# Options Trading System - Design Document

## Overview

The Options Trading System extends Northstar v3 with institutional-grade options trading capabilities. The system integrates with Upstox API for live options data, implements regime-based strategy selection, enforces strict risk controls, and provides comprehensive position tracking with tax-aware P&L calculation.

### Design Philosophy

1. **Safety First**: Multiple layers of validation prevent catastrophic losses
2. **Regime-Driven**: Market conditions dictate strategy selection, not emotions
3. **Manual Execution**: System generates signals; human executes trades
4. **Tax Reality**: All P&L calculations include India's 30% VDA tax
5. **Integration**: Seamless integration with existing Northstar v3 infrastructure

### Key Design Decisions

- **Adapter Pattern**: Upstox adapter replaces yfinance for options only; equities unchanged
- **Immutable Ledger**: All trades stored in append-only parquet files
- **State-Driven**: Leverages existing UnifiedState for temporal consistency
- **Risk Hierarchy**: Options risk validators integrate with existing RiskCoordinator
- **Observer Pattern**: Dashboard observers monitor options state changes
- **V3 Nervous System**: Deep integration with V3 organs (not bolt-on sidecar)
- **Institutional Discipline**: Risk has veto power, edge decay monitored, silence mode enforced

## V3 Nervous System Integration

### Integration Philosophy

The options system is **not** a separate module that talks to V3 via APIs. It is an **organ** within the V3 organism, sharing the same nervous system (UnifiedState), obeying the same risk authority (RiskCoordinator), and thinking with the same intelligence (MarketBrain, CrisisEngine, PulseState).

This deep integration provides:
1. **Temporal Integrity**: TemporalGuard prevents lookahead bias
2. **Correlation Control**: Equity regime gates options strategies
3. **Anticipatory Defense**: Crisis engine provides lead time
4. **Micro-Timing Edge**: Pulse state improves entry/exit timing
5. **Epistemic Sizing**: Confidence state modulates position size
6. **Capital Competition**: Bayesian allocation across strategies
7. **Absolute Authority**: Risk coordinator has veto power
8. **Auditable Behavior**: Event bus enables replay and post-mortems
9. **Edge Hygiene**: Signal decay monitor prevents silent death
10. **Historical Intuition**: Regime memory informs aggressiveness

### V3 Integration Map

```
┌─────────────────────────────────────────────────────────────────┐
│                    NORTHSTAR V3 ORGANISM                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              UNIFIED STATE (Brainstem)                    │  │
│  │  - EquityState                                            │  │
│  │  - OptionsState ◄─── NEW ORGAN                           │  │
│  │  - RiskState                                              │  │
│  │  - PerformanceState                                       │  │
│  └──────────────────────────────────────────────────────────┘  │
│                            ▲                                     │
│                            │                                     │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │           TEMPORAL GUARD (Time Integrity)                 │  │
│  │  Wraps: Option Chain Fetch, IV History, Regime Detection │  │
│  └──────────────────────────────────────────────────────────┘  │
│                            ▲                                     │
│                            │                                     │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              MARKET BRAIN (Intelligence)                  │  │
│  │  - MarketState.regime ──► Options Regime Gating          │  │
│  │  - CrisisEngine ──► Forced Exits & Strategy Bans         │  │
│  │  - PulseState ──► Micro-Timing Filter                    │  │
│  │  - ConfidenceState ──► Position Sizing Modulation        │  │
│  │  - RegimeMemory ──► Historical Context                   │  │
│  └──────────────────────────────────────────────────────────┘  │
│                            ▲                                     │
│                            │                                     │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │         OPTIONS REGIME DETECTION ENGINE                   │  │
│  │  Inputs: IV Rank, Skew, Vol-of-Vol, Equity Regime        │  │
│  │  Output: Options Regime (5 types)                         │  │
│  └──────────────────────────────────────────────────────────┘  │
│                            ▼                                     │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │       OPTIONS STRATEGY INTELLIGENCE ORGAN                 │  │
│  │  - Basic: IC, Calendar, Straddle                          │  │
│  │  - Advanced: Micro-Calendar, Skew Harvest, Post-Event    │  │
│  │  - Meta: Edge Scoring, Fatigue Detection, Silence Mode   │  │
│  └──────────────────────────────────────────────────────────┘  │
│                            ▼                                     │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │         RISK COORDINATOR (Absolute Authority)             │  │
│  │  - OptionsRiskValidator ◄─── NEW VALIDATOR               │  │
│  │  - Kill Switches (Weekly Loss, Trauma, Portfolio Cap)    │  │
│  │  - Emergency Brake (Force Close Authority)               │  │
│  │  - Veto Power Over All Trades                            │  │
│  └──────────────────────────────────────────────────────────┘  │
│                            ▼                                     │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │         BAYESIAN CAPITAL TRIBUNAL                         │  │
│  │  Options as Strategy Sleeve                               │  │
│  │  Competes with Equities for Capital                       │  │
│  │  Allocation Based on Edge Score + Regret Risk             │  │
│  └──────────────────────────────────────────────────────────┘  │
│                            ▼                                     │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              POSITION MANAGEMENT                          │  │
│  │  - MTM Calculation                                        │  │
│  │  - Portfolio Greeks Aggregation                           │  │
│  │  - Exit Condition Monitoring                              │  │
│  └──────────────────────────────────────────────────────────┘  │
│                            ▼                                     │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              EVENT BUS (Auditable Actions)                │  │
│  │  - OPTIONS_REGIME_CHANGE                                  │  │
│  │  - OPTIONS_TRADE_SIGNAL                                   │  │
│  │  - OPTIONS_KILL_SWITCH                                    │  │
│  │  - PORTFOLIO_GREEKS_BREACH                                │  │
│  └──────────────────────────────────────────────────────────┘  │
│                            ▼                                     │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │         VALIDATION FRAMEWORK (Edge Hygiene)               │  │
│  │  - SignalDecayMonitor ──► IV Edge Decay                  │  │
│  │  - NoEdgeDetector ──► Strategy Pause                     │  │
│  │  - RedundancyMonitor ──► Strategy Overlap                │  │
│  └──────────────────────────────────────────────────────────┘  │
│                            ▼                                     │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │         BRAIN WINDOW (Dashboard)                          │  │
│  │  - OptionsPanel ◄─── NEW PANEL                           │  │
│  │  - Regime vs Equity Regime Display                        │  │
│  │  - Portfolio Greeks Time Series                           │  │
│  │  - Kill Switch Reasons                                    │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### Critical Integration Points

#### 1. UnifiedState Integration (Mandatory)
**File**: `src/core/state.py` or `src/state/unified_state_manager.py`

**OptionsState Schema**:
```python
@dataclass
class OptionsState:
    # Regime
    current_regime: Regime
    regime_history: List[Tuple[datetime, Regime]]
    days_in_regime: int
    regime_metrics: RegimeMetrics
    
    # Positions
    open_positions: Dict[str, Position]
    closed_positions: List[Position]
    
    # Portfolio Greeks
    portfolio_greeks: Greeks
    greek_history: List[Tuple[datetime, Greeks]]
    
    # Risk Tracking
    weekly_risk_usage: float  # 0.0 to 1.0
    weekly_trades_count: int
    ytd_tax_liability: float
    
    # Kill Switches
    kill_switch_active: bool
    kill_switch_reasons: List[str]
    kill_switch_cooldown_until: Optional[datetime]
    trauma_cooldown_until: Optional[datetime]
    
    # Performance
    equity_high_water_mark: float
    current_equity: float
    current_risk_pct: float
    
    # Strategy Intelligence
    strategy_edge_scores: Dict[str, float]
    strategy_fatigue_flags: Dict[str, bool]
```

**Integration**:
- Add `OptionsState` to `UnifiedState` dataclass
- Options state changes flow through `UnifiedStateManager.update_state()`
- Temporal snapshots include options state
- State transitions auditable via event bus

#### 2. TemporalGuard Integration (Non-Negotiable)
**File**: `src/cohesion/temporal_guard.py`

**Wrapped Operations**:
```python
# Option chain fetches
@temporal_guard.enforce_point_in_time
def fetch_option_chain(self, underlying: str, expiry: date, as_of: datetime) -> pd.DataFrame:
    # Ensures no future data leakage
    pass

# IV history access
@temporal_guard.enforce_lookback_window
def get_iv_history(self, underlying: str, lookback_days: int, as_of: datetime) -> pd.Series:
    # Ensures only past data accessed
    pass

# Regime detection
@temporal_guard.validate_inputs
def detect_regime(self, option_chain: pd.DataFrame, iv_history: pd.Series, as_of: datetime) -> Regime:
    # Validates all inputs are point-in-time consistent
    pass

# MTM calculation
@temporal_guard.enforce_point_in_time
def calculate_mtm(self, position: Position, current_chain: pd.DataFrame, as_of: datetime) -> float:
    # Ensures MTM uses correct timestamp data
    pass
```

**Validation Rules**:
- No future timestamps in data
- Expiry dates validated against current time
- Historical data access enforces lookback limits
- Temporal violations logged as CRITICAL

#### 3. MarketState Correlation Control
**File**: `src/state/market_state.py`

**Regime Gating Logic**:
```python
def check_equity_regime_gate(equity_regime: str, options_strategy: StrategyType) -> bool:
    """Hard gate based on equity regime"""
    
    if equity_regime == "CRISIS":
        # Only allow defined-risk long-vol
        return options_strategy in [StrategyType.LONG_STRADDLE]
    
    elif equity_regime == "HIGH_STRESS":
        # Block all short-vol
        return options_strategy not in [StrategyType.IRON_CONDOR, StrategyType.CALENDAR_SPREAD]
    
    elif equity_regime == "NORMAL":
        # Full regime logic applies
        return True
    
    elif equity_regime == "LOW_VOL":
        # Allow condors but with tighter bands
        return True
    
    return False
```

**Integration**:
- Read `MarketState.regime` from existing V3 state
- Apply hard gates before strategy generation
- Log correlation regime matrix for post-mortems
- Force-close positions on regime flip to CRISIS

#### 4. CrisisEngine Integration
**Files**: `src/intelligence/crisis_engine.py`, `src/intelligence/shock_detector.py`

**Event Subscriptions**:
```python
# Subscribe to crisis events
crisis_engine.subscribe("shock_detected", on_shock_detected)
crisis_engine.subscribe("crisis_probability_high", on_crisis_probability_high)
crisis_engine.subscribe("correlation_spike", on_correlation_spike)

def on_shock_detected(event: CrisisEvent):
    """Reduce position sizes by 50%"""
    for position in open_positions:
        if position.is_short_vol():
            position.reduce_size(0.5)
            log_event("POSITION_SIZE_REDUCED", reason="shock_detected")

def on_crisis_probability_high(event: CrisisEvent):
    """Force-close all short-vol positions"""
    for position in open_positions:
        if position.is_short_vol():
            force_close_position(position, reason="crisis_probability_high")

def on_correlation_spike(event: CrisisEvent):
    """Block new short-vol for 48 hours"""
    set_kill_switch("correlation_spike", cooldown_hours=48)
```

**Lead Time Advantage**:
- Crisis engine detects patterns before equity drawdowns show
- Options exit before panic IV explodes
- Anticipatory defense, not reactive

#### 5. PulseState Timing Filter
**File**: `src/state/pulse_state.py` (if exists) or integrate with MarketState

**Timing Rules**:
```python
def check_pulse_timing(pulse_state: PulseState, action: str) -> bool:
    """Use pulse for micro-timing"""
    
    if action == "ENTRY":
        # Block entries during pulse spikes
        if pulse_state.intensity > 0.7:
            return False  # Market stress too high
        
        # Delay selling vol if pulse building
        if pulse_state.phase == "BUILDING" and is_short_vol_strategy():
            return False  # Wait for expansion
    
    elif action == "EXIT":
        # Tighten exit targets if pulse hostile
        if pulse_state.risk_level == "HIGH":
            tighten_exit_target(0.10)  # 10% tighter
    
    return True
```

**Edge Source**:
- Pulse captures micro-stress better than IV alone
- Retail traders don't have this timing signal
- Timing alpha, not strategy alpha

#### 6. Confidence & Belief State Sizing
**Files**: `src/intelligence/confidence_engine.py`, `src/state/belief_state.py`

**Position Sizing Modulation**:
```python
def calculate_position_size(
    base_size: float,
    confidence_state: ConfidenceState,
    belief_state: BeliefState,
    iv_rank: float
) -> float:
    """Modulate size based on epistemic certainty"""
    
    # High IV + Low confidence → skip
    if iv_rank > 0.7 and confidence_state.level < 0.4:
        return 0.0
    
    # Moderate IV + High confidence → full size
    if 0.4 < iv_rank < 0.7 and confidence_state.level > 0.7:
        return base_size
    
    # Low IV + Medium confidence → half size
    if iv_rank < 0.4 and 0.4 < confidence_state.level < 0.7:
        return base_size * 0.5
    
    # Default: scale linearly with confidence
    return base_size * confidence_state.level
```

**Rare Edge**:
- Most systems size only by capital
- This sizes by epistemic certainty
- Rare even in professional desks

#### 7. Bayesian Capital Allocation
**File**: `src/portfolio/bayesian_capital_tribunal.py` or `src/portfolio/capital_allocator.py`

**Multi-Strategy Competition**:
```python
def allocate_capital(
    strategies: List[Strategy],
    total_capital: float,
    performance_history: Dict[str, PerformanceMetrics]
) -> Dict[str, float]:
    """Allocate capital probabilistically across strategies"""
    
    allocations = {}
    
    for strategy in strategies:
        # Calculate edge score
        edge_score = calculate_edge_score(strategy, performance_history)
        
        # Calculate regret risk
        regret_risk = calculate_regret_risk(strategy, performance_history)
        
        # Bayesian allocation
        allocation = (edge_score / (1 + regret_risk)) * total_capital
        
        allocations[strategy.name] = allocation
    
    # Normalize to total capital
    return normalize_allocations(allocations, total_capital)
```

**Prevents**:
- Over-trading options
- Revenge sizing
- Options hijacking portfolio capital

#### 8. RiskCoordinator Absolute Authority
**File**: `src/risk/risk_coordinator.py` or `src/risk/unified_risk_coordinator.py`

**OptionsRiskValidator**:
```python
class OptionsRiskValidator(RiskValidator):
    """Options-specific risk validator for RiskCoordinator"""
    
    def validate(self, trade: Trade, portfolio: Portfolio, state: UnifiedState) -> RiskValidationResult:
        """Validate options trade against system-level risk rules"""
        
        violations = []
        
        # Check kill switches
        if state.options.kill_switch_active:
            violations.append("Options kill switch active")
        
        # Check portfolio drawdown
        if portfolio.drawdown > 0.05:  # 5% drawdown
            violations.append("Portfolio drawdown exceeds 5%")
        
        # Check volatility shock
        if state.market.volatility_shock_detected:
            violations.append("Volatility shock detected")
        
        # Check portfolio risk cap
        total_risk = sum(pos.max_loss for pos in state.options.open_positions.values())
        if total_risk + trade.max_loss > 0.02 * portfolio.capital:
            violations.append("Portfolio risk cap exceeded")
        
        return RiskValidationResult(
            approved=len(violations) == 0,
            violations=violations,
            veto_authority="RiskCoordinator"
        )
```

**Integration**:
- Register `OptionsRiskValidator` in RiskCoordinator hierarchy
- Options trades subject to all system-level risk rules
- RiskCoordinator can force-close options positions
- Emergency brake applies to options

#### 9. Event Bus Integration
**File**: `src/core/events.py` or existing event bus

**Options Events**:
```python
class OptionsEvent(Enum):
    REGIME_CHANGE = "options_regime_change"
    TRADE_SIGNAL = "options_trade_signal"
    KILL_SWITCH = "options_kill_switch"
    GREEKS_BREACH = "portfolio_greeks_breach"
    POSITION_OPENED = "options_position_opened"
    POSITION_CLOSED = "options_position_closed"
    EDGE_DECAY = "options_edge_decay"
    STRATEGY_FATIGUE = "options_strategy_fatigue"

@dataclass
class OptionsEventData:
    event_type: OptionsEvent
    timestamp: datetime
    regime: Optional[Regime]
    reason: str
    metrics: Dict[str, Any]
    decision_path: List[str]
```

**Publishing**:
```python
# Publish regime change
event_bus.publish(OptionsEvent.REGIME_CHANGE, {
    "old_regime": old_regime,
    "new_regime": new_regime,
    "iv_rank": iv_rank,
    "days_in_old_regime": days
})

# Publish trade signal
event_bus.publish(OptionsEvent.TRADE_SIGNAL, {
    "strategy_type": strategy.type,
    "regime": current_regime,
    "max_loss": strategy.max_loss,
    "edge_score": edge_score
})

# Publish kill switch
event_bus.publish(OptionsEvent.KILL_SWITCH, {
    "reason": "weekly_loss_limit",
    "cooldown_until": cooldown_date,
    "weekly_loss": weekly_loss
})
```

**Benefits**:
- Enables replay for debugging
- Enables post-mortem analysis
- Dashboard subscribes for real-time updates
- Immutable audit trail

#### 10. Validation Framework Integration
**Files**: `src/validation/signal_decay_monitor.py`, `src/validation/no_edge_detector.py`, `src/validation/redundancy_monitor.py`

**Edge Decay Monitoring**:
```python
class OptionsEdgeMonitor:
    """Monitor options strategy edge decay"""
    
    def monitor_edge_decay(self, strategy_type: str, recent_trades: List[Trade]) -> EdgeDecayMetrics:
        """Detect if strategy edge is decaying"""
        
        # Calculate rolling metrics
        win_rate = calculate_win_rate(recent_trades, window=20)
        avg_profit = calculate_avg_profit(recent_trades, window=20)
        exit_timing = calculate_avg_exit_timing(recent_trades, window=20)
        
        # Detect decay
        edge_decaying = (
            win_rate < historical_win_rate * 0.8 or  # 20% drop
            avg_profit < historical_avg_profit * 0.7 or  # 30% drop
            exit_timing < historical_exit_timing * 0.8  # Exiting earlier
        )
        
        if edge_decaying:
            # Pause strategy
            pause_strategy(strategy_type, reason="edge_decay_detected")
            
            # Alert
            alert("EDGE_DECAY", f"{strategy_type} edge decaying")
        
        return EdgeDecayMetrics(
            win_rate=win_rate,
            avg_profit=avg_profit,
            exit_timing=exit_timing,
            edge_decaying=edge_decaying
        )
```

**Prevents**:
- Silent edge erosion
- Slow death from strategy fatigue
- Continued trading when edge gone

#### 11. RegimeMemory Integration
**File**: `src/intelligence/memory.py` or `src/intelligence/regime_memory_system.py`

**Historical Context**:
```python
def compare_to_historical_regimes(
    current_iv_surface: pd.DataFrame,
    regime_memory: RegimeMemorySystem
) -> RegimeSimilarity:
    """Compare current regime to historical similar regimes"""
    
    # Find similar past regimes
    similar_regimes = regime_memory.find_similar(
        iv_rank=current_iv_rank,
        skew=current_skew,
        vol_of_vol=current_vol_of_vol,
        similarity_threshold=0.8
    )
    
    # Analyze outcomes
    past_outcomes = [r.outcome for r in similar_regimes]
    
    # Adjust aggressiveness
    if any(o.was_crash for o in past_outcomes):
        # Current regime similar to past crash
        reduce_aggressiveness(0.5)
        log("REGIME_MEMORY", "Similar to past crash - reducing aggressiveness")
    
    elif all(o.was_profitable for o in past_outcomes):
        # Current regime similar to past success
        maintain_aggressiveness()
        log("REGIME_MEMORY", "Similar to past success - maintaining aggressiveness")
    
    return RegimeSimilarity(
        similar_regimes=similar_regimes,
        aggressiveness_adjustment=adjustment
    )
```

**Rare Capability**:
- Algorithmic historical intuition
- Almost no retail systems have this
- Prevents repeated regime mistakes

### Integration Data Flow

```
Market Reality (NSE)
        ↓
Upstox API
        ↓
TemporalGuard ◄─── Enforces point-in-time consistency
        ↓
Data Normalization
        ↓
UnifiedState ◄─── All state changes flow here
        ↓
┌───────────────────────────────────────────────┐
│  Intelligence Layer (V3 Organs)               │
│  - MarketState.regime                         │
│  - CrisisEngine                               │
│  - PulseState                                 │
│  - ConfidenceState                            │
│  - RegimeMemory                               │
└───────────────────────────────────────────────┘
        ↓
Options Regime Detection ◄─── Uses V3 intelligence
        ↓
Strategy Intelligence Organ ◄─── Edge scoring, fatigue detection
        ↓
Trade Eligibility Validation
        ↓
RiskCoordinator ◄─── Absolute veto authority
        ↓
Bayesian Capital Allocation ◄─── Competes with equities
        ↓
Position Management
        ↓
Event Bus ◄─── Auditable actions
        ↓
Dashboard (Brain Window) ◄─── Real-time observability
```

### Why This Integration Matters

**Without V3 Integration** (Retail Approach):
- Options trade in isolation
- No correlation awareness
- Reactive to crises
- Blind to edge decay
- Capital sizing by rules
- No temporal integrity
- Limited observability

**With V3 Integration** (Institutional Approach):
- Options as first-class organ
- Correlation gates enforced
- Anticipatory crisis defense
- Continuous edge monitoring
- Probabilistic capital allocation
- Temporal integrity guaranteed
- Full audit trail and replay

This is the difference between:
❌ Trading options
✅ Controlling derivatives risk

The integration is not optional. It's what makes the system institutional-grade.

## Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────────┐
│                    Options Trading System                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────────┐      ┌──────────────────┐                │
│  │  Upstox Adapter  │──────│  Data Pipeline   │                │
│  │  (Live Options)  │      │  (Normalization) │                │
│  └──────────────────┘      └──────────────────┘                │
│           │                          │                           │
│           ▼                          ▼                           │
│  ┌─────────────────────────────────────────────┐               │
│  │         Regime Detection Engine              │               │
│  │  (IV Rank, Skew, Vol-of-Vol, Events)       │               │
│  └─────────────────────────────────────────────┘               │
│           │                                                      │
│           ▼                                                      │
│  ┌─────────────────────────────────────────────┐               │
│  │       Strategy Generation Engine             │               │
│  │  (Iron Condor, Calendar, Straddle)          │               │
│  └─────────────────────────────────────────────┘               │
│           │                                                      │
│           ▼                                                      │
│  ┌─────────────────────────────────────────────┐               │
│  │      Trade Eligibility Validator             │               │
│  │  (Liquidity, Events, Vol-of-Vol, Hygiene)   │               │
│  └─────────────────────────────────────────────┘               │
│           │                                                      │
│           ▼                                                      │
│  ┌─────────────────────────────────────────────┐               │
│  │         Capital Scaling Engine               │               │
│  │  (Performance-Based Risk Adjustment)         │               │
│  └─────────────────────────────────────────────┘               │
│           │                                                      │
│           ▼                                                      │
│  ┌─────────────────────────────────────────────┐               │
│  │          Survival Rules Engine               │               │
│  │  (Kill Switches, Circuit Breakers)           │               │
│  └─────────────────────────────────────────────┘               │
│           │                                                      │
│           ▼                                                      │
│  ┌─────────────────────────────────────────────┐               │
│  │        Position Management System            │               │
│  │  (Tracking, MTM, Greeks, Exit Logic)         │               │
│  └─────────────────────────────────────────────┘               │
│           │                                                      │
│           ▼                                                      │
│  ┌─────────────────────────────────────────────┐               │
│  │         Tax-Aware P&L Tracker                │               │
│  │  (Gross, Costs, Tax, Net P&L)                │               │
│  └─────────────────────────────────────────────┘               │
│           │                                                      │
│           ▼                                                      │
│  ┌─────────────────────────────────────────────┐               │
│  │         Dashboard Integration                │               │
│  │  (Options Panel, Greek Charts, Alerts)       │               │
│  └─────────────────────────────────────────────┘               │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### Integration with Northstar v3

The options system integrates with existing v3 components:

1. **UnifiedState**: Options positions and metrics stored in state
2. **RiskCoordinator**: Options risk validators added to hierarchy
3. **Dashboard**: New OptionsObserver and OptionsPanel components
4. **Event Bus**: Options events published to existing bus
5. **Audit Trail**: Options trades logged to immutable ledger

### Data Flow

```
Upstox API → Adapter → Normalization → Regime Detection
                                              ↓
                                       Strategy Generation
                                              ↓
                                       Eligibility Check
                                              ↓
                                       Capital Scaling
                                              ↓
                                       Survival Rules
                                              ↓
                                       Signal Output
                                              ↓
                                    [Manual Execution]
                                              ↓
                                       Position Tracking
                                              ↓
                                       P&L Calculation
                                              ↓
                                       Dashboard Display
```

## Components and Interfaces

### 1. Upstox Adapter

**Purpose**: Fetch live options data from Upstox API and normalize to pipeline format

**Interface**:
```python
class UpstoxAdapter:
    def __init__(self, api_key: str, api_secret: str, access_token: str)
    def fetch_option_chain(self, underlying: str, expiry: date) -> pd.DataFrame
    def fetch_option_greeks(self, instrument_keys: List[str]) -> pd.DataFrame
    def refresh_token(self) -> str
    def get_underlying_price(self, symbol: str) -> float
```

**Key Methods**:
- `fetch_option_chain()`: Uses Upstox **Put/Call Option Chain API** (`/v2/option/chain`) to fetch complete option chain data including bid/ask prices, quantities, Greeks, and IV in a single call. Returns DataFrame with columns: symbol, expiry, strike, option_type, bid, ask, ltp, iv, delta, gamma, theta, vega, oi, prev_oi, volume, underlying_price, bid_qty, ask_qty
- `fetch_option_greeks()`: Uses Upstox **Option Greeks API** (`/v3/market-quote/option-greek`) for real-time Greek updates. Supports up to 50 instrument keys per request. Returns DataFrame with: instrument_key, last_price, ltq, volume, cp, iv, vega, gamma, theta, delta, oi
- `refresh_token()`: Handles OAuth token refresh automatically
- Rate limiting: Max 1 request per second, exponential backoff on errors

**API Endpoints Used**:
1. **Option Chain**: `GET /v2/option/chain?instrument_key={underlying_key}&expiry_date={expiry}`
   - Returns complete option chain with market data and Greeks
   - Includes bid/ask prices and quantities for liquidity checks
   - Provides PCR (Put-Call Ratio) for each strike
   
2. **Option Greeks**: `GET /v3/market-quote/option-greek?instrument_key={keys}`
   - Real-time Greek updates for up to 50 instruments
   - Used for intraday position monitoring
   - Lower latency than full option chain fetch

**Data Normalization**:
- Input: Upstox API JSON response (nested structure with call_options/put_options)
- Output: Flattened parquet-compatible DataFrame matching existing pipeline schema
- Validation: Check for missing fields, invalid strikes, negative Greeks, bid_qty/ask_qty presence

### 2. Regime Detection Engine

**Purpose**: Classify current options market regime based on volatility metrics

**Interface**:
```python
class RegimeDetector:
    def detect_regime(self, option_chain: pd.DataFrame, underlying_regime: str) -> Regime
    def calculate_iv_rank(self, current_iv: float, iv_history: pd.Series) -> float
    def calculate_skew(self, option_chain: pd.DataFrame) -> float
    def check_vol_of_vol(self, iv_history: pd.Series) -> bool
```

**Regime Types**:
```python
class Regime(Enum):
    LOW_VOL_SELL = "low_vol_sell"      # IV rank > 70%, stable vol, equity regime not CRISIS
    HIGH_VOL_SELL = "high_vol_sell"    # IV rank > 80%, elevated vol, equity regime not CRISIS
    RISING_VOL_BUY = "rising_vol_buy"  # IV rank < 30%, vol expanding
    NEUTRAL = "neutral"                 # No clear regime
    CRASH_HEDGE = "crash_hedge"         # Extreme conditions or equity regime = CRISIS
```

**Correlation Regime Handling**:
The system integrates with Northstar v3's existing equity regime detection to handle correlation risk:

- **If underlying equity regime = CRISIS**:
  - Block all short-vol strategies (iron condor, calendar spread)
  - Allow only defined-risk long-vol strategies (long straddle)
  - Force-close all open short-vol positions
  - Reason: Correlation spikes during crisis make short-vol extremely dangerous

This creates a hard gate that prevents catastrophic losses during market contagion events (banking stress, global risk-off, etc.).

**Regime Detection Logic**:
1. Calculate IV percentile rank: Rank current IV against 252-day history, convert to percentile (0-100%)
2. Calculate IV position (min-max normalized): `(current_iv - min_iv_252d) / (max_iv_252d - min_iv_252d)`
3. Calculate IV trend: 5-day vs 20-day moving average
4. Calculate skew: (OTM put IV - ATM IV) / ATM IV
5. Check vol-of-vol: `std(iv_5d) > 1.5 * std(iv_20d)`
6. Check underlying equity regime from existing v3 system
7. Combine all inputs to determine options regime

**Important Distinction**:
- **IV Rank** (percentile): Used for regime thresholds (e.g., "IV rank > 70%")
- **IV Position** (min-max): Used for relative positioning within range
- All regime thresholds in this document refer to **IV percentile rank**

**Regime Persistence**:
- Regime must persist ≥ 2 trading days before allowing trades
- Stored in UnifiedState with timestamp history
- Regime changes trigger position review

### 3. Strategy Generation Engine

**Purpose**: Generate appropriate option strategies based on current regime

**Interface**:
```python
class StrategyGenerator:
    def generate_strategies(self, regime: Regime, option_chain: pd.DataFrame, 
                           capital: float, risk_pct: float) -> List[OptionStrategy]
    def calculate_strategy_metrics(self, strategy: OptionStrategy) -> StrategyMetrics
```

**Strategy Types**:
```python
@dataclass
class OptionStrategy:
    strategy_type: str  # "iron_condor", "calendar_spread", "long_straddle"
    legs: List[OptionLeg]
    max_loss: float
    max_profit: float
    net_credit_debit: float
    breakevens: List[float]
    greeks: Greeks
    expiry: date
    underlying: str
    underlying_price: float

@dataclass
class OptionLeg:
    symbol: str
    strike: float
    option_type: str  # "call" or "put"
    action: str  # "buy" or "sell"
    quantity: int  # Must be whole lot sizes
    premium: float
    iv: float
    delta: float
    gamma: float
    theta: float
    vega: float
```

**Strategy Generation Rules**:

**Iron Condor** (LOW_VOL_SELL):
- Sell OTM call and put (16-20 delta)
- Buy further OTM call and put for protection (5-10 delta)
- Width: 100-200 points for NIFTY, 200-400 for BANKNIFTY
- Net credit ≥ 0.25 × max loss
- Expiry: 15-30 days out

**Calendar Spread** (HIGH_VOL_SELL):
- Sell near-term ATM option (7-14 days)
- Buy far-term ATM option (30-45 days)
- Net debit trade
- Profit from theta decay differential
- Max loss = net debit paid

**Calendar Spread Risk Classification**:
- Calendars are **conditional short-vol** strategies
- Blocked under vol-of-vol elevation (same as iron condors)
- Blocked under trauma rule (same as iron condors)
- **NOT** automatically blocked under pure delta shocks (unlike iron condors)
- This distinction matters: calendars can survive directional moves better than iron condors

**Long Straddle** (RISING_VOL_BUY):
- Buy ATM call and put (same strike, same expiry)
- Expiry: 30-60 days out
- Max loss = total premium paid
- Profit from large moves in either direction

**Lot Size Validation**:
- NIFTY: 50 units per lot
- BANKNIFTY: 15 units per lot
- All quantities must be whole multiples of lot size
- Reject strategies requiring fractional lots

### 4. Trade Eligibility Validator

**Purpose**: Enforce strict eligibility rules before allowing trades

**Interface**:
```python
class TradeEligibilityValidator:
    def validate_trade(self, strategy: OptionStrategy, regime: Regime, 
                      event_calendar: EventCalendar) -> ValidationResult
    def check_liquidity(self, legs: List[OptionLeg]) -> bool
    def check_event_calendar(self, expiry: date, calendar: EventCalendar) -> bool
    def check_vol_of_vol(self, iv_history: pd.Series) -> bool
```

**Validation Checks**:

1. **Regime Persistence**: Regime must be stable for ≥ 2 days
2. **IV Rank Thresholds**:
   - LOW_VOL_SELL: IV rank > 70%
   - HIGH_VOL_SELL: IV rank > 80%
   - RISING_VOL_BUY: IV rank < 30%
3. **Liquidity Check**: Bid-ask spread ≤ 8% of mid premium
4. **Liquidity Depth**: `bid_qty ≥ 2 × required_lot_size`
5. **Expiry Hygiene**: No new trades with < 5 days to expiry
6. **Event Calendar**: Block short-vol within 2 days of macro events
7. **Vol-of-Vol**: Block short-vol if `std(iv_5d) > 1.5 * std(iv_20d)`
8. **Late-Cycle Protection**: Reduce size by 50% if LOW_VOL_SELL > 10 days
9. **Premium Adequacy**: Net credit ≥ 0.25 × max loss (for credit spreads)

**Event Calendar**:
```python
@dataclass
class MacroEvent:
    event_type: str  # "RBI", "CPI", "WPI", "Budget", "Election"
    date: date
    buffer_days: int  # Days before/after to block short-vol
```

### 5. Capital Scaling Engine

**Purpose**: Dynamically adjust risk per trade based on performance

**Interface**:
```python
class CapitalScalingEngine:
    def calculate_risk_per_trade(self, performance: PerformanceMetrics) -> float
    def check_scaling_eligibility(self, weeks_live: int, trades: List[Trade]) -> bool
    def update_scaling_state(self, new_trade: Trade) -> None
```

**Scaling Rules**:

**Base Parameters**:
- Base capital: ₹5,00,000
- Base risk: 1.0% per trade (₹5,000)
- Max risk ceiling: 1.5% per trade (₹7,500)

**Profit Scaling**:
- +0.25% risk after each 8% net profit milestone
- Example: At 8% profit, risk becomes 1.25%
- Example: At 16% profit, risk becomes 1.5% (capped)

**Drawdown De-Scaling**:
- -0.25% risk at 3% drawdown (risk becomes 0.75%)
- -0.50% risk at 5% drawdown (risk becomes 0.5%)
- Recovery: Risk increases only after equity reaches previous high + 2 profitable trades

**Time Requirement**:
- No scaling before 8 consecutive weeks of live trading
- Prevents premature scaling on limited data

**State Tracking**:
```python
@dataclass
class ScalingState:
    current_risk_pct: float
    equity_high_water_mark: float
    current_equity: float
    weeks_live: int
    consecutive_wins: int
    last_scaling_event: date
```

### 6. Survival Rules Engine

**Purpose**: Implement circuit breakers to prevent catastrophic losses

**Interface**:
```python
class SurvivalRulesEngine:
    def check_kill_switches(self, portfolio: OptionsPortfolio, 
                           performance: PerformanceMetrics) -> KillSwitchStatus
    def check_weekly_loss_limit(self, weekly_pnl: float, capital: float) -> bool
    def check_trauma_rule(self, recent_trades: List[Trade]) -> bool
    def check_portfolio_risk_cap(self, open_positions: List[Position]) -> bool
```

**Kill Switch Rules**:

1. **Weekly Loss Kill Switch**:
   - Halt trading if weekly loss ≥ 2% capital
   - **Trade counting window**: Monday 00:00 IST to Sunday 23:59 IST
   - **Loss aggregation window**: Monday 00:00 IST to Sunday 23:59 IST
   - **Reset window**: Monday 9:15 AM IST (after NSE market open)
   - Respects NSE holidays (no reset on holiday Mondays)
   - Override: Requires manual approval + 48h cooling period

**Boundary Clarification**:
- Trades executed Sunday 23:59 count toward the ending week
- Loss calculation resets at Monday 9:15 AM IST (not midnight)
- This 9.25-hour gap (00:00-09:15) allows for overnight risk assessment before market open

**Time Zone and Calendar**:
- All times referenced in this document are **IST (Indian Standard Time)**
- Weekly resets follow **NSE trading calendar** (excludes holidays)
- Monday morning block: 9:15 AM - 10:00 AM IST
- Expiry day blocks: Thursday (weekly expiry), last Thursday of month (monthly expiry)

2. **Single-Trade Trauma Rule**:
   - No short-vol for 2 weeks if any trade loses > 80% max loss
   - Applies to iron condors and calendar spreads
   - Long straddles exempt (defined risk)

3. **Portfolio Risk Cap**:
   - Total open worst-case loss ≤ 2% capital
   - Sum of max_loss across all open positions
   - Reject new trades if cap would be exceeded

4. **Tax Reality Check**:
   - Halt if YTD tax payable > cash buffer
   - Cash buffer = 30% of YTD gross profits
   - Prevents liquidity crisis at tax payment time

5. **Frequency Limits**:
   - Max 2 trades per week (hard limit)
   - No trading on Monday mornings (9:15-10:00)
   - No trading on expiry days (Thursday for weekly, last Thursday for monthly)

**Kill Switch Status**:
```python
@dataclass
class KillSwitchStatus:
    active: bool
    triggered_rules: List[str]
    cooldown_until: Optional[date]
    override_allowed: bool
    reason: str
```

### 7. Position Management System

**Purpose**: Track open positions, calculate MTM, monitor Greeks, execute exits

**Interface**:
```python
class PositionManager:
    def open_position(self, strategy: OptionStrategy, entry_time: datetime) -> Position
    def update_position_mtm(self, position: Position, current_chain: pd.DataFrame) -> Position
    def check_exit_conditions(self, position: Position, regime: Regime) -> ExitSignal
    def close_position(self, position: Position, exit_time: datetime, exit_prices: Dict) -> Trade
    def calculate_portfolio_greeks(self, positions: List[Position]) -> Greeks
```

**Position Object**:
```python
@dataclass
class Position:
    position_id: str
    strategy_type: str
    regime_at_entry: Regime
    legs: List[PositionLeg]
    entry_time: datetime
    expiry: date
    max_loss: float
    max_profit: float
    entry_credit_debit: float
    current_value: float
    unrealized_pnl: float
    realized_pnl: float
    days_held: int
    greeks: Greeks
    exit_time: Optional[datetime]
    exit_reason: Optional[str]

@dataclass
class PositionLeg:
    symbol: str
    strike: float
    option_type: str
    action: str
    quantity: int
    entry_premium: float
    current_premium: float
    entry_iv: float
    current_iv: float
    delta: float
    gamma: float
    theta: float
    vega: float
```

**Mark-to-Market Calculation**:
- Daily MTM using live option chain data
- Current value = sum of (current_premium × quantity × action_multiplier)
- Action multiplier: +1 for buy, -1 for sell
- Unrealized P&L = current_value - entry_credit_debit

**Exit Rules**:

1. **Profit Target**: Close at 55% of max profit
2. **Stop Loss**: Close at 40% of max loss
3. **Time Decay**: Close 2 days before expiry
4. **Regime Flip**: Close if regime changes from entry regime
5. **Greek Violations**: Close if portfolio Greeks exceed safety bands

**Exit Rule Precedence** (when multiple triggers fire simultaneously):
1. Stop-loss (highest priority - protects capital)
2. Gamma escalation (risk containment)
3. Regime flip (market condition change)
4. Time decay (expiry management)
5. Profit target (lowest priority - optimization)

The highest priority rule determines the exit reason logged in the trade ledger.

**Greek Safety Bands**:
- Delta: [-0.2, +0.2] (near delta-neutral)
- Theta: Positive (time decay working for us)
- Vega: [-0.3, +0.1] (limited vol exposure)
- Gamma: No hard block, but monitored for risk escalation

**Gamma Risk Escalation**:
While gamma has no hard limit, the following conditions trigger forced exits:
- Gamma spike (>2x entry gamma) + negative theta → immediate exit
- Gamma spike + regime flip → immediate exit
- Gamma spike + underlying equity regime = CRISIS → immediate exit

Gamma risk is continuously monitored but only enforced when combined with other risk factors.

**Portfolio Greeks Aggregation**:
```python
@dataclass
class Greeks:
    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float  # Optional, less critical for short-term trades
```

### 8. Tax-Aware P&L Tracker

**Purpose**: Calculate accurate post-tax P&L for all trades

**Interface**:
```python
class TaxAwarePnLTracker:
    def calculate_gross_pnl(self, entry_value: float, exit_value: float) -> float
    def calculate_costs(self, legs: List[PositionLeg]) -> TradeCosts
    def calculate_tax(self, gross_pnl: float) -> float
    def calculate_net_pnl(self, gross_pnl: float, costs: TradeCosts, tax: float) -> float
    def track_ytd_tax_liability(self, trades: List[Trade]) -> float
```

**Cost Structure**:
```python
@dataclass
class TradeCosts:
    brokerage: float  # ₹20 per leg
    exchange_charges: float  # ~0.05% of turnover
    sebi_charges: float  # ₹10 per crore
    stamp_duty: float  # 0.003% on buy side
    gst: float  # 18% on brokerage + exchange charges
    total: float
```

**Cost Calculation**:
- Brokerage: ₹20 per leg (entry + exit)
- Exchange charges: 0.05% of premium × quantity
- SEBI charges: ₹10 per ₹1 crore turnover
- Stamp duty: 0.003% on buy-side premium
- GST: 18% on (brokerage + exchange charges)

**Tax Calculation** (India VDA Regime):
- Tax rate: 30% flat on profits
- **Tax timing**: Applied on trade close date, not on unrealized MTM
- No tax accrual on unrealized P&L (only on closed trades)
- No loss offset across financial years
- Tax on gross profit before costs
- YTD tax liability = sum of (max(0, gross_pnl) × 0.30) for all closed trades

This timing distinction is critical for dashboard display and audit trails.

**Net P&L Formula**:
```
Net P&L = Gross P&L - Total Costs - Tax
```

**Trade Rejection Rule**:
- Reject trade if expected net P&L < 1.5 × total costs
- Ensures minimum profitability threshold
- Prevents churning for marginal gains

### 9. Dashboard Integration

**Purpose**: Integrate options trading into existing Northstar v3 dashboard

**Components**:

**OptionsObserver** (Observer Pattern):
```python
class OptionsObserver:
    def on_regime_change(self, event: StateEvent) -> None
    def on_position_update(self, event: StateEvent) -> None
    def on_trade_signal(self, event: StateEvent) -> None
    def on_kill_switch(self, event: StateEvent) -> None
```

**OptionsPanel** (Streamlit Component):
- Live regime display with IV rank and trend
- Active positions table with P&L and Greeks
- Portfolio Greeks chart (time series)
- Trade history with win rate and metrics
- Risk metrics: weekly risk used, capital scaling status
- Kill switch status with reasons
- Next trade eligibility with blocking reasons

**Dashboard Layout**:
```
┌─────────────────────────────────────────────────────────┐
│  Options Trading Panel                                  │
├─────────────────────────────────────────────────────────┤
│  Current Regime: LOW_VOL_SELL (3 days)                 │
│  IV Rank: 75% | IV Trend: Stable | Vol-of-Vol: Normal  │
├─────────────────────────────────────────────────────────┤
│  Active Positions (2)                                   │
│  ┌───────────────────────────────────────────────────┐ │
│  │ Strategy  | Strikes | P&L    | Days | Greeks     │ │
│  │ Iron Cond | 21500/  | +₹2.1k | 5    | Δ:-0.05   │ │
│  │           | 22500   |        |      | Θ:+150    │ │
│  └───────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────┤
│  Portfolio Greeks (Chart)                               │
│  [Time series line chart of Delta, Theta, Vega]        │
├─────────────────────────────────────────────────────────┤
│  Risk Metrics                                           │
│  Weekly Risk Used: 1/2 trades | Capital Scaling: 1.0%  │
│  Kill Switch: ✓ Active (Weekly Loss Limit)             │
├─────────────────────────────────────────────────────────┤
│  Next Trade Eligibility                                 │
│  ✗ Blocked: Weekly loss limit exceeded                 │
│  ✓ Regime stable for 3 days                            │
│  ✓ No macro events in next 2 days                      │
└─────────────────────────────────────────────────────────┘
```

## Data Models

### Configuration Schema

**options_trading.yaml**:
```yaml
capital:
  base_capital: 500000
  base_risk_pct: 1.0
  max_risk_pct: 1.5
  
upstox:
  api_key: ${UPSTOX_API_KEY}
  api_secret: ${UPSTOX_API_SECRET}
  access_token: ${UPSTOX_ACCESS_TOKEN}
  rate_limit_per_second: 1
  endpoints:
    option_chain: "https://api.upstox.com/v2/option/chain"
    option_greeks: "https://api.upstox.com/v3/market-quote/option-greek"
    market_quote: "https://api.upstox.com/v2/market-quote/quotes"
  max_instruments_per_request: 50  # For option greeks API
  
strategies:
  allowed:
    - iron_condor
    - calendar_spread
    - long_straddle
  
  iron_condor:
    short_delta_range: [0.16, 0.20]
    long_delta_range: [0.05, 0.10]
    width_nifty: [100, 200]
    width_banknifty: [200, 400]
    min_credit_ratio: 0.25
    expiry_days: [15, 30]
  
  calendar_spread:
    near_term_days: [7, 14]
    far_term_days: [30, 45]
    strike_selection: "ATM"
  
  long_straddle:
    strike_selection: "ATM"
    expiry_days: [30, 60]

regime_detection:
  iv_rank_lookback_days: 252
  vol_of_vol_threshold: 1.5
  regime_persistence_days: 2
  
  thresholds:
    low_vol_sell_iv_rank: 0.70
    high_vol_sell_iv_rank: 0.80
    rising_vol_buy_iv_rank: 0.30

eligibility:
  max_bid_ask_spread_pct: 0.08
  min_liquidity_depth_multiplier: 2.0
  min_days_to_expiry: 5
  event_buffer_days: 2
  late_cycle_days: 10
  late_cycle_size_reduction: 0.5

capital_scaling:
  profit_milestone_pct: 0.08
  profit_scaling_increment: 0.0025
  drawdown_threshold_1: 0.03
  drawdown_threshold_2: 0.05
  drawdown_descaling_1: 0.0025
  drawdown_descaling_2: 0.005
  min_weeks_before_scaling: 8
  recovery_profitable_trades: 2

survival_rules:
  weekly_loss_limit_pct: 0.02
  trauma_loss_threshold_pct: 0.80
  trauma_cooldown_weeks: 2
  portfolio_risk_cap_pct: 0.02
  max_trades_per_week: 2
  no_trade_times:
    - day: "Monday"
      start: "09:15"
      end: "10:00"
  no_trade_days:
    - "Thursday"  # Weekly expiry

exit_rules:
  profit_target_pct: 0.55
  stop_loss_pct: 0.40
  days_before_expiry: 2
  
greek_safety_bands:
  delta_min: -0.2
  delta_max: 0.2
  theta_min: 0.0
  vega_min: -0.3
  vega_max: 0.1

costs:
  brokerage_per_leg: 20
  exchange_charges_pct: 0.0005
  sebi_charges_per_crore: 10
  stamp_duty_pct: 0.00003
  gst_pct: 0.18

tax:
  rate: 0.30  # India VDA regime
  min_profitability_multiplier: 1.5

event_calendar:
  - event_type: "RBI"
    dates:
      - "2024-02-08"
      - "2024-04-05"
      - "2024-06-07"
      - "2024-08-08"
      - "2024-10-09"
      - "2024-12-06"
    buffer_days: 2
  
  - event_type: "CPI"
    dates:
      - "2024-01-12"
      - "2024-02-12"
      # ... monthly releases
    buffer_days: 2
  
  - event_type: "Budget"
    dates:
      - "2024-02-01"
    buffer_days: 3

lot_sizes:
  NIFTY: 50
  BANKNIFTY: 15

dashboard:
  refresh_interval_seconds: 5
  greek_chart_lookback_days: 30
  trade_history_limit: 50
```

### Database Schema

**Trade Ledger** (Parquet, Append-Only):
```python
trade_ledger_schema = {
    'trade_id': 'string',
    'timestamp': 'datetime64[ns]',
    'action': 'string',  # 'open' or 'close'
    'strategy_type': 'string',
    'regime_at_entry': 'string',
    'underlying': 'string',
    'expiry': 'datetime64[ns]',
    'legs': 'string',  # JSON serialized
    'entry_credit_debit': 'float64',
    'exit_value': 'float64',
    'gross_pnl': 'float64',
    'costs': 'float64',
    'tax': 'float64',
    'net_pnl': 'float64',
    'days_held': 'int32',
    'exit_reason': 'string',
    'greeks_at_entry': 'string',  # JSON serialized
    'greeks_at_exit': 'string',  # JSON serialized
}
```

**Position State** (In UnifiedState):
```python
position_state_schema = {
    'position_id': 'string',
    'status': 'string',  # 'open', 'closed'
    'strategy_type': 'string',
    'regime_at_entry': 'string',
    'entry_time': 'datetime64[ns]',
    'expiry': 'datetime64[ns]',
    'legs': List[PositionLeg],
    'max_loss': 'float64',
    'max_profit': 'float64',
    'current_value': 'float64',
    'unrealized_pnl': 'float64',
    'greeks': Greeks,
}
```

**Regime History** (In UnifiedState):
```python
regime_history_schema = {
    'timestamp': 'datetime64[ns]',
    'regime': 'string',
    'iv_rank': 'float64',
    'iv_trend': 'string',
    'vol_of_vol_elevated': 'bool',
    'underlying_regime': 'string',
    'days_in_regime': 'int32',
}
```


### Performance Metrics Schema

**Scaling State** (In UnifiedState):
```python
scaling_state_schema = {
    'current_risk_pct': 'float64',
    'equity_high_water_mark': 'float64',
    'current_equity': 'float64',
    'weeks_live': 'int32',
    'consecutive_wins': 'int32',
    'last_scaling_event': 'datetime64[ns]',
    'scaling_history': List[ScalingEvent],
}
```

**Kill Switch State** (In UnifiedState):
```python
kill_switch_state_schema = {
    'active': 'bool',
    'triggered_rules': List[str],
    'cooldown_until': 'datetime64[ns]',
    'weekly_loss': 'float64',
    'weekly_trades_count': 'int32',
    'last_trauma_date': 'datetime64[ns]',
    'trauma_cooldown_until': 'datetime64[ns]',
}
```

## Error Handling

### API Error Handling

**Upstox API Errors**:
1. **Token Expiration**: Automatic refresh, fallback to cached data
2. **Rate Limiting**: Exponential backoff (1s, 2s, 4s, 8s)
3. **Network Errors**: Retry 3 times, then graceful degradation
4. **Invalid Response**: Log error, skip current cycle, alert user
5. **Timeout**: 10-second timeout, retry once

**Error Recovery Strategy**:
```python
def fetch_with_retry(func, max_retries=3, backoff_base=1.0):
    for attempt in range(max_retries):
        try:
            return func()
        except TokenExpiredError:
            refresh_token()
            continue
        except RateLimitError:
            time.sleep(backoff_base * (2 ** attempt))
            continue
        except NetworkError as e:
            if attempt == max_retries - 1:
                log_error(e)
                return use_cached_data()
            time.sleep(backoff_base)
            continue
    raise MaxRetriesExceeded()
```

### Data Validation Errors

**Schema Validation**:
- Missing required fields → Reject data, log error, alert
- Invalid data types → Attempt coercion, reject if fails
- Out-of-range values → Flag as suspicious, manual review
- Negative Greeks → Log warning, use absolute value if appropriate

**Temporal Validation**:
- Future timestamps → Reject immediately, log critical error
- Stale data (> 5 minutes old) → Flag warning, use with caution
- Missing historical data → Interpolate if possible, otherwise skip

### Trading Logic Errors

**Strategy Generation Errors**:
- No valid strikes found → Skip signal, log reason
- Lot size constraints violated → Reject strategy
- Premium inadequacy → Reject strategy, log metrics

**Position Management Errors**:
- MTM calculation failure → Use last known value, alert
- Greek calculation error → Set to zero, flag for review
- Exit signal failure → Manual intervention required

**Risk Validation Errors**:
- Kill switch activation → Halt all trading, alert immediately
- Greek violation → Close position, log reason
- Portfolio risk cap exceeded → Reject new trades

### System Errors

**State Management Errors**:
- State corruption → Rollback to last snapshot, alert
- Event bus failure → Log error, continue with degraded functionality
- Audit trail write failure → Critical error, halt system

**Dashboard Errors**:
- Rendering failure → Show error message, continue background processing
- Data refresh failure → Use cached data, show staleness indicator
- Observer notification failure → Log error, continue

### Logging Strategy

**Log Levels**:
- **DEBUG**: Detailed execution flow, data transformations
- **INFO**: Normal operations, trade signals, regime changes
- **WARNING**: Recoverable errors, data quality issues, near-limit conditions
- **ERROR**: Failed operations, rejected trades, validation failures
- **CRITICAL**: System failures, kill switch activations, data corruption

**Structured Logging Format**:
```python
{
    'timestamp': '2024-01-15T10:30:00Z',
    'level': 'INFO',
    'component': 'regime_detector',
    'event': 'regime_change',
    'data': {
        'old_regime': 'NEUTRAL',
        'new_regime': 'LOW_VOL_SELL',
        'iv_rank': 0.75,
        'days_in_old_regime': 5
    }
}
```

### Alert Strategy

**Critical Alerts** (Immediate notification):
- Kill switch activation
- API token expiration
- Data corruption detected
- System crash or unhandled exception

**Warning Alerts** (Batched, hourly):
- Trade rejection due to eligibility
- Greek safety band violations
- Approaching risk limits
- Data quality issues

**Info Alerts** (Daily summary):
- Regime changes
- Trade signals generated
- Position updates
- Performance metrics

## Testing Strategy

The options trading system requires comprehensive testing across multiple dimensions to ensure correctness, safety, and reliability.

### Unit Testing

**Purpose**: Verify individual components work correctly in isolation

**Coverage Areas**:
1. **Data Normalization**: Upstox API response → DataFrame conversion
2. **Regime Detection**: IV rank calculation, vol-of-vol checks
3. **Strategy Generation**: Strike selection, lot size validation, Greek calculation
4. **Eligibility Validation**: Each validation rule independently
5. **Capital Scaling**: Profit/drawdown scaling logic
6. **Survival Rules**: Kill switch triggers
7. **Position Management**: MTM calculation, exit condition checks
8. **P&L Calculation**: Cost calculation, tax calculation, net P&L

**Example Unit Tests**:
```python
def test_iv_rank_calculation():
    """Test IV rank calculation with known values"""
    current_iv = 20.0
    iv_history = pd.Series([15.0, 18.0, 22.0, 25.0, 20.0])
    expected_rank = 0.5  # (20-15)/(25-15)
    assert calculate_iv_rank(current_iv, iv_history) == expected_rank

def test_lot_size_validation():
    """Test that fractional lots are rejected"""
    strategy = create_iron_condor(quantity=37)  # Not multiple of 50
    assert not validate_lot_size(strategy, lot_size=50)

def test_weekly_loss_kill_switch():
    """Test kill switch activates at 2% weekly loss"""
    weekly_pnl = -10000  # -2% of 500k capital
    capital = 500000
    assert check_weekly_loss_limit(weekly_pnl, capital) == True
```

### Property-Based Testing

**Purpose**: Verify universal properties hold across all valid inputs

Property-based tests will be written after completing the prework analysis in the next section. Each correctness property from the design will be implemented as a property-based test with minimum 100 iterations.

**Property Test Configuration**:
- Library: `hypothesis` (Python)
- Iterations: 100 minimum per property
- Seed: Fixed for reproducibility
- Shrinking: Enabled for minimal failing examples
- Tag format: `# Feature: options-trading-system, Property {N}: {property_text}`

### Integration Testing

**Purpose**: Verify components work together correctly

**Test Scenarios**:
1. **End-to-End Signal Generation**:
   - Fetch option chain → Detect regime → Generate strategy → Validate eligibility
   - Verify signal output format and completeness

2. **Position Lifecycle**:
   - Open position → Daily MTM updates → Exit condition triggered → Close position
   - Verify P&L calculation and ledger entry

3. **Kill Switch Integration**:
   - Simulate weekly loss → Verify kill switch activates → Verify trading halted
   - Test cooldown period and reset logic

4. **Dashboard Integration**:
   - Publish state events → Verify observer notifications → Verify panel updates
   - Test real-time data flow

### Stress Testing

**Purpose**: Verify system behavior under extreme conditions

**Stress Scenarios**:
1. **Vol Expansion**: Simulate IV spike from 15% to 50% in 2 days
2. **Calendar Spread Failure**: Simulate near-term option losing 80% value
3. **Consecutive Losses**: Simulate 5 consecutive losing trades
4. **API Downtime**: Simulate Upstox API unavailable for 1 hour
5. **Data Corruption**: Simulate malformed API responses
6. **Rapid Regime Changes**: Simulate regime flipping daily for 1 week

**Expected Behaviors**:
- Kill switches activate appropriately
- No trades executed during API downtime
- Graceful degradation with cached data
- No data corruption in ledger
- Risk limits enforced under all conditions

### Backtesting

**Purpose**: Validate strategy rules with historical data

**Backtest Requirements**:
1. **Historical Option Chain Data**: 1 year of daily option chains
2. **Realistic Slippage**: 1-2% slippage on entry/exit
3. **All Costs Included**: Brokerage, taxes, exchange charges
4. **Regime Persistence**: Enforce 2-day regime stability
5. **Event Calendar**: Include historical macro events

**Backtest Metrics**:
- Win rate (target: > 60%)
- Average profit per trade (target: > ₹3,000 net)
- Max drawdown (target: < 8%)
- Sharpe ratio (target: > 1.5)
- Greek violations (target: 0)
- Kill switch activations (target: < 2 per year)

**Simulation Period**: 8 weeks minimum, 6 months ideal

### Validation Framework Integration

The options system integrates with Northstar v3's existing validation framework:

1. **Schema Validation**: All data inputs validated against schemas
2. **Temporal Validation**: No lookahead bias in backtests
3. **Walk-Forward Testing**: Out-of-sample validation on rolling windows
4. **Signal Decay Monitoring**: Track if strategy performance degrades over time

### Test Data Management

**Mock Data**:
- Synthetic option chains with realistic Greeks
- Controlled regime transitions
- Predictable P&L outcomes

**Historical Data**:
- Real Upstox API responses (anonymized)
- Actual market conditions from 2023-2024
- Real macro event dates

**Test Fixtures**:
- Pre-configured strategies for each regime
- Sample positions at various P&L levels
- Event calendar with known dates

### Continuous Testing

**Pre-Commit Checks**:
- Unit tests must pass
- Code coverage > 80%
- Linting and type checking

**Daily Validation**:
- Integration tests on staging
- Backtest on recent 30 days
- Data quality checks

**Weekly Validation**:
- Full backtest on 6 months
- Stress test scenarios
- Performance regression checks


## Correctness Properties

A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.

The following properties define the correctness criteria for the options trading system. Each property is universally quantified (applies to all valid inputs) and references the specific requirements it validates.

### Data Integrity Properties

**Property 1: API Data Completeness**
*For any* option chain fetched from Upstox API, the resulting DataFrame must contain all required fields: symbol, expiry, strike, option_type, bid, ask, ltp, iv, delta, gamma, theta, vega, oi, change_oi, volume, underlying_price, bid_qty, ask_qty.
**Validates: Requirements US-1.2**

**Property 2: Data Normalization Round-Trip**
*For any* valid Upstox API response, normalizing the data to parquet format and then validating against the pipeline schema should succeed without errors.
**Validates: Requirements US-1.3**

**Property 3: Adapter Interface Compatibility**
*For any* data source adapter (yfinance or Upstox), calling the same interface method with equivalent parameters should produce DataFrames with identical schemas and compatible data types.
**Validates: Requirements US-1.4**

**Property 4: Rate Limiting Enforcement**
*For any* sequence of API calls made within a 1-second window, the system should throttle requests to ensure no more than 1 request per second is sent to the Upstox API.
**Validates: Requirements US-1.6**

**Property 5: Trade Ledger Immutability**
*For any* trade ledger file, once a record is written, the record count should only increase (never decrease), and existing records should never be modified (append-only).
**Validates: Requirements US-7.6**

### Regime Detection Properties

**Property 6: Regime Classification Domain**
*For any* valid option chain and IV history, the regime detector must return exactly one of the five valid regime types: LOW_VOL_SELL, HIGH_VOL_SELL, RISING_VOL_BUY, NEUTRAL, or CRASH_HEDGE.
**Validates: Requirements US-2.1**

**Property 7: Regime Input Sensitivity**
*For any* regime detection calculation, changing any of the four inputs (IV rank, IV trend, skew, underlying regime) should either change the output regime or be demonstrably considered in the calculation logic.
**Validates: Requirements US-2.2**

**Property 8: Regime Persistence Requirement**
*For any* regime that has persisted for fewer than 2 trading days, trade eligibility validation should reject all trade signals with reason "regime not stable".
**Validates: Requirements US-2.3, US-4.1**

**Property 9: Vol-of-Vol Short-Vol Block**
*For any* IV history where the 5-day standard deviation exceeds 1.5 times the 20-day standard deviation, all short-vol strategies (iron condor, calendar spread) should be rejected with reason "elevated vol-of-vol".
**Validates: Requirements US-2.5, US-4.7**

### Strategy Generation Properties

**Property 10: Regime-Strategy Mapping**
*For any* valid option chain, the strategy generator should produce:
- Iron Condor strategies when regime is LOW_VOL_SELL
- Calendar Spread strategies when regime is HIGH_VOL_SELL
- Long Straddle strategies when regime is RISING_VOL_BUY
**Validates: Requirements US-3.1, US-3.2, US-3.3**

**Property 11: Strategy Data Completeness**
*For any* generated option strategy, the strategy object must contain all required fields: strategy_type, legs, max_loss, max_profit, net_credit_debit, breakevens, greeks, expiry, underlying, underlying_price.
**Validates: Requirements US-3.4**

**Property 12: Lot Size Constraint**
*For any* generated strategy, all leg quantities must be whole multiples of the underlying's lot size (50 for NIFTY, 15 for BANKNIFTY).
**Validates: Requirements US-3.5**

**Property 13: Premium Adequacy**
*For any* credit spread strategy (iron condor), the net credit must be at least 25% of the maximum loss (net_credit ≥ 0.25 × max_loss).
**Validates: Requirements US-3.6**

### Trade Eligibility Properties

**Property 14: IV Rank Threshold Enforcement**
*For any* strategy in a given regime, the current IV rank must meet the regime's threshold:
- LOW_VOL_SELL: IV rank > 70%
- HIGH_VOL_SELL: IV rank > 80%
- RISING_VOL_BUY: IV rank < 30%
**Validates: Requirements US-4.2**

**Property 15: Liquidity Spread Check**
*For any* option leg in a proposed strategy, if the bid-ask spread exceeds 8% of the mid premium, the trade should be rejected with reason "insufficient liquidity".
**Validates: Requirements US-4.3**

**Property 16: Liquidity Depth Check**
*For any* option leg in a proposed strategy, if the bid quantity is less than 2 times the required lot size, the trade should be rejected with reason "insufficient depth".
**Validates: Requirements US-4.4**

**Property 17: Expiry Hygiene**
*For any* proposed strategy, if the expiry date is less than 5 trading days away, the trade should be rejected with reason "expiry too soon".
**Validates: Requirements US-4.5**

**Property 18: Event Calendar Block**
*For any* short-vol strategy (iron condor, calendar spread), if there is a macro event (RBI, CPI, WPI, Budget) within 2 days before or after the current date, the trade should be rejected with reason "macro event proximity".
**Validates: Requirements US-4.6**

**Property 19: Late-Cycle Size Reduction**
*For any* strategy in LOW_VOL_SELL regime that has persisted for more than 10 days, the calculated position size should be 50% of the base position size.
**Validates: Requirements US-4.8**

### Capital Scaling Properties

**Property 20: Risk Ceiling Invariant**
*For any* calculated risk percentage, regardless of profit or drawdown state, the risk per trade must never exceed 1.5% of capital.
**Validates: Requirements US-5.3**

**Property 21: Profit Scaling Trigger**
*For any* performance state where net profit reaches an 8% milestone (8%, 16%, 24%, etc.), the risk per trade should increase by 0.25% from the previous level (subject to the 1.5% ceiling).
**Validates: Requirements US-5.2**

**Property 22: Drawdown De-Scaling**
*For any* performance state:
- If drawdown reaches 3%, risk should decrease by 0.25%
- If drawdown reaches 5%, risk should decrease by 0.50%
**Validates: Requirements US-5.4**

**Property 23: Recovery Condition**
*For any* performance state in drawdown, risk should not increase unless both conditions are met: (1) equity reaches previous high water mark, AND (2) 2 consecutive profitable trades have occurred.
**Validates: Requirements US-5.5**

**Property 24: Scaling Time Requirement**
*For any* scaling calculation, if the system has been live for fewer than 8 consecutive weeks, the risk per trade should remain at the base level (1.0%) regardless of profit or drawdown.
**Validates: Requirements US-5.6**

### Survival Rules Properties

**Property 25: Weekly Loss Kill Switch**
*For any* weekly P&L calculation, if the loss reaches or exceeds 2% of capital, the kill switch should activate and block all new trades until the next Monday 9:15 AM.
**Validates: Requirements US-6.1**

**Property 26: Trauma Rule Activation**
*For any* closed trade that loses more than 80% of its maximum loss, short-vol strategies (iron condor, calendar spread) should be blocked for 2 weeks from the trade close date.
**Validates: Requirements US-6.2**

**Property 27: Portfolio Risk Cap**
*For any* portfolio of open positions, the sum of maximum losses across all positions must not exceed 2% of capital. New trades that would violate this cap should be rejected.
**Validates: Requirements US-6.3**

**Property 28: Tax Liquidity Check**
*For any* YTD performance state, if the calculated tax liability (30% of YTD gross profits) exceeds the cash buffer, the kill switch should activate with reason "tax liquidity risk".
**Validates: Requirements US-6.4**

**Property 29: Weekly Trade Frequency Limit**
*For any* week (Monday 00:00 to Sunday 23:59), the number of executed trades must not exceed 2. The third trade attempt should be rejected with reason "weekly limit reached".
**Validates: Requirements US-6.5**

**Property 30: Time-Based Trade Blocks**
*For any* trade signal generated on Monday between 9:15-10:00 AM or on an expiry day (Thursday), the trade should be rejected with reason "blocked time window".
**Validates: Requirements US-6.6**

### Position Management Properties

**Property 31: Position Data Completeness**
*For any* open position, the position object must contain all required fields: position_id, strategy_type, regime_at_entry, legs, entry_time, expiry, max_loss, max_profit, entry_credit_debit, current_value, unrealized_pnl, greeks.
**Validates: Requirements US-7.1**

**Property 32: MTM Responsiveness**
*For any* position, when mark-to-market is calculated with new option chain data, if the option premiums have changed, the position's current_value and unrealized_pnl must be updated to reflect the new premiums.
**Validates: Requirements US-7.2**

**Property 33: Exit Condition Triggers**
*For any* position, an exit signal should be generated if any of these conditions are met:
- Unrealized P&L reaches 55% of max profit
- Unrealized P&L reaches 40% of max loss
- Days to expiry ≤ 2
- Current regime differs from regime at entry
**Validates: Requirements US-7.3**

**Property 34: Portfolio Greeks Aggregation**
*For any* portfolio of positions, the portfolio Greeks (delta, gamma, theta, vega) should equal the sum of the corresponding Greeks from all individual positions.
**Validates: Requirements US-7.4**

**Property 35: Greek Safety Band Violations**
*For any* portfolio Greeks calculation:
- If delta < -0.2 or delta > +0.2, trigger alert
- If theta < 0, trigger alert
- If vega < -0.3 or vega > +0.1, trigger alert
- If gamma > 2× entry gamma AND (theta < 0 OR regime flipped OR equity regime = CRISIS), trigger forced exit
**Validates: Requirements US-7.5**

### P&L Calculation Properties

**Property 36: Gross P&L Formula**
*For any* closed position, the gross P&L should equal the exit value minus the entry credit/debit (gross_pnl = exit_value - entry_credit_debit).
**Validates: Requirements US-8.1**

**Property 37: Cost Completeness**
*For any* trade, the total costs must include all five components: brokerage (₹20 per leg), exchange charges (~0.05% of turnover), SEBI charges (₹10 per crore), stamp duty (0.003% on buy side), and GST (18% on brokerage + exchange charges).
**Validates: Requirements US-8.2**

**Property 38: Tax Calculation**
*For any* closed trade:
- If gross P&L > 0, tax = 0.30 × gross_pnl
- If gross P&L ≤ 0, tax = 0
**Validates: Requirements US-8.3**

**Property 39: Net P&L Formula**
*For any* closed trade, the net P&L should equal gross P&L minus total costs minus tax (net_pnl = gross_pnl - costs - tax).
**Validates: Requirements US-8.4**

**Property 40: Minimum Profitability Filter**
*For any* proposed trade, if the expected net P&L is less than 1.5 times the estimated total costs, the trade should be rejected with reason "insufficient expected profit".
**Validates: Requirements US-8.5**

**Property 41: YTD Tax Liability Aggregation**
*For any* set of closed trades in the current financial year, the YTD tax liability should equal the sum of taxes on all profitable trades (sum of max(0, gross_pnl) × 0.30).
**Validates: Requirements US-8.6**

### Dashboard and Reporting Properties

**Property 42: Trade History Metrics**
*For any* set of closed trades, the calculated metrics (win rate, average profit, max drawdown) should be mathematically consistent with the individual trade P&Ls.
**Validates: Requirements US-9.5**

**Property 43: Trade Rejection Reasons**
*For any* rejected trade, the eligibility validator must provide at least one specific reason for the rejection (e.g., "regime not stable", "insufficient liquidity", "weekly limit reached").
**Validates: Requirements US-9.7**

### System Hygiene Properties

**Property 44: Strategy Concentration Limit**
*For any* sequence of trades, no more than 2 consecutive trades should be of the same strategy type. The third consecutive trade of the same type should be rejected with reason "strategy concentration limit".
**Validates: Requirements US-10.1**

**Property 45: Success Cooling Period**
*For any* sequence of trades, after 2 consecutive winning trades, the next trade signal should be skipped (unless IV rank is extreme: >90% or <10%) with reason "success cooling period".
**Validates: Requirements US-10.2**

**Property 46: Equity Crisis Regime Block**
*For any* proposed short-vol strategy (iron condor, calendar spread), if the underlying equity regime (from Northstar v3) is classified as CRISIS, the trade should be rejected with reason "equity crisis regime - correlation risk".
**Validates: Requirements US-2.1, US-2.2** (implicit correlation handling)

### Backtesting Properties

**Property 47: Backtest Cost Inclusion**
*For any* backtest simulation, the final P&L must include all cost components (brokerage, exchange charges, SEBI charges, stamp duty, GST) and taxes (30% on profits), not just gross P&L.
**Validates: Requirements US-12.3**

