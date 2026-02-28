# Requirements Document

## Introduction

The High-Conviction Engine represents a fundamental architectural transformation of Northstar V3 from a safety-first trading system to an asymmetry-focused, high-conviction trading engine. This transformation prioritizes capturing large market moves through sustained conviction rather than minimizing drawdowns through defensive mechanisms.

## Glossary

- **System**: The High-Conviction Trading Engine
- **V3_System**: The existing Northstar V3 trading system
- **Conviction_Contract**: A commitment mechanism that locks in trading parameters and prevents fear-based modifications
- **Exposure_State**: Discrete position sizing levels (RISK_OFF: 0-20%, NEUTRAL: 40-60%, RISK_ON: 80-100%)
- **Regime_Engine**: Module that determines market supportiveness for trend-following
- **Trend_Engine**: Module that identifies and validates market trends
- **Alpha_Thesis**: The core edge hypothesis about market behavior
- **Shutdown_Controller**: Module that enforces maximum drawdown covenant
- **Truth_Review**: Monthly reflection process without system interference
- **Shadow_Trading**: Validation process using paper trading before live deployment

## Requirements

### Requirement 1: Psychological Foundation

**User Story:** As a trader, I want psychological safeguards that maintain conviction during drawdowns, so that I don't abandon profitable strategies due to temporary discomfort.

#### Acceptance Criteria

1. WHEN the System initializes, THE System SHALL create a Conviction_Contract that locks commitment parameters for the trading period
2. WHEN market drawdowns occur, THE System SHALL prevent modifications to core trading logic through anti-override mechanisms
3. WHEN prolonged discomfort periods arise, THE System SHALL maintain exposure according to predetermined rules without human intervention
4. WHEN fear-based modification attempts are detected, THE System SHALL log the attempt and maintain original parameters
5. THE System SHALL accept drawdowns up to -18% as part of normal operation without reducing conviction

### Requirement 2: Alpha Thesis Implementation

**User Story:** As a systematic trader, I want a single, focused edge implementation, so that I can maximize returns from my core thesis without signal dilution.

#### Acceptance Criteria

1. THE System SHALL implement exactly one alpha thesis: "Markets trend longer and more violently than most participants expect when macro conditions, liquidity, and price action align"
2. WHEN multiple trend signals are available, THE System SHALL focus on late-stage continuation patterns rather than early reversal timing
3. THE System SHALL eliminate all competing strategy signals that dilute the core thesis
4. WHEN trend conditions are met, THE System SHALL maintain positions until structural invalidation occurs
5. THE System SHALL reject any signal that contradicts the primary alpha thesis

### Requirement 3: Exposure Reengineering

**User Story:** As a conviction-based trader, I want discrete exposure states that express belief levels, so that position sizing reflects conviction rather than fear management.

#### Acceptance Criteria

1. THE System SHALL operate in exactly three exposure states: RISK_OFF (0-20%), NEUTRAL (40-60%), RISK_ON (80-100%)
2. WHEN exposure transitions occur, THE System SHALL move directly between states without intermediate throttling
3. THE System SHALL treat exposure as expression of market belief rather than liability management
4. THE System SHALL eliminate all micro-control mechanisms including small stops, daily dampening, and frequent rebalancing
5. WHEN in RISK_ON state, THE System SHALL maintain 80-100% exposure until regime or trend invalidation

### Requirement 4: Risk Redefinition

**User Story:** As a long-term trader, I want risk defined as premature exit rather than drawdown size, so that I can capture full trend moves without being stopped out early.

#### Acceptance Criteria

1. THE System SHALL define risk as "exiting before thesis plays out" rather than drawdown magnitude
2. WHEN drawdowns reach -18%, THE System SHALL execute hard shutdown rather than gradual reduction
3. THE System SHALL create loss taxonomy separating process failure from thesis failure
4. THE System SHALL maintain positions through temporary drawdowns if thesis remains valid
5. WHEN maximum drawdown is breached, THE System SHALL shut down completely rather than reduce exposure

### Requirement 5: V3 Module Restructuring

**User Story:** As a system architect, I want to eliminate comfort-optimizing modules, so that the system maintains conviction over safety.

#### Acceptance Criteria

1. THE System SHALL archive the existing V3_System to preserve historical functionality
2. THE System SHALL retain only core authoritative modules: RegimeEngine, TrendEngine, ShutdownController, ExposureStateMachine, PositionSizer, ExitController
3. THE System SHALL demote intelligence modules to read-only diagnostics without exposure authority
4. THE System SHALL delete all micro-control, smoothing, and fear-based override systems
5. THE System SHALL eliminate approximately 60-75% of existing V3 modules that optimize for comfort

### Requirement 6: Signal Architecture

**User Story:** As a systematic trader, I want binary regime signals with clear hierarchy, so that trend decisions are only made in supportive market conditions.

#### Acceptance Criteria

1. THE System SHALL generate binary regime signals: SUPPORTIVE or HOSTILE based on liquidity, volatility, and policy conditions
2. WHEN regime is HOSTILE, THE System SHALL disable all trend signal processing
3. WHEN regime is SUPPORTIVE, THE System SHALL activate trend signal evaluation
4. THE System SHALL prevent trend signals from overriding regime decisions
5. THE System SHALL evaluate signals on weekly cadence without intraday panic reactions

### Requirement 7: Position Sizing Logic

**User Story:** As a conviction trader, I want deterministic position sizing based on exposure state only, so that sizing reflects systematic rules rather than emotional responses.

#### Acceptance Criteria

1. THE System SHALL calculate position sizes based solely on current exposure state
2. THE System SHALL eliminate P&L-based resizing, volatility targeting, and confidence scaling
3. THE System SHALL apply equal weight allocation with signal strength multipliers: Strong (1.5x), Normal (1.0x), Weak (0.75x)
4. WHEN exposure state changes, THE System SHALL recalculate all position sizes immediately
5. THE System SHALL maintain consistent sizing methodology regardless of recent performance

### Requirement 8: Exit Logic

**User Story:** As a trend follower, I want structural exits only, so that I capture full trend moves without premature profit-taking or fear-based exits.

#### Acceptance Criteria

1. THE System SHALL exit positions only on: regime flip, trend invalidation, or shutdown event
2. THE System SHALL explicitly forbid drawdown-based exits, profit-taking, volatility-based exits, and news reactions
3. WHEN trend remains valid and regime supportive, THE System SHALL maintain positions regardless of unrealized P&L
4. WHEN structural exit conditions are met, THE System SHALL exit all affected positions immediately
5. THE System SHALL log all exit decisions with structural reasoning

### Requirement 9: Accountability Systems

**User Story:** As a systematic trader, I want complete decision transparency, so that I can learn from outcomes without interfering with live trading.

#### Acceptance Criteria

1. THE System SHALL create immutable logs of all signals, exposures, trades, and override attempts
2. THE System SHALL conduct monthly Truth_Reviews for reflection without system interference
3. THE System SHALL validate all logic through Shadow_Trading before live deployment
4. WHEN decisions are logged, THE System SHALL include timestamp, reasoning, and market context
5. THE System SHALL prevent any modification of historical decision logs

### Requirement 10: Implementation Phases

**User Story:** As a system implementer, I want phased deployment with validation gates, so that the transformation is systematic and validated at each step.

#### Acceptance Criteria

1. WHEN Phase 1 begins, THE System SHALL archive V3_System and create northstar_c namespace
2. WHEN Phase 2 executes, THE System SHALL build only Tier-1 authoritative modules
3. WHEN Phase 3 starts, THE System SHALL enforce 90-day discipline period with no additional features
4. WHEN Phase 4 begins, THE System SHALL conduct Shadow_Trading validation for minimum 30 days
5. WHEN Phase 5 launches, THE System SHALL deploy live trading with covenant enforcement active

### Requirement 11: Property-Based Validation

**User Story:** As a system validator, I want comprehensive property-based testing, so that the system behavior is mathematically verified under all conditions.

#### Acceptance Criteria

1. THE System SHALL validate that exposure state transitions follow rules exactly through property-based testing
2. THE System SHALL verify that no unauthorized exposure modifications occur through comprehensive test coverage
3. THE System SHALL confirm shutdown triggers activate at precise thresholds through boundary testing
4. THE System SHALL ensure decision logging captures all system behavior through audit trail validation
5. THE System SHALL prove override prevention mechanisms function under stress through adversarial testing

### Requirement 12: Psychological Pressure Resistance

**User Story:** As a conviction trader, I want the system to resist human interference during stress, so that optimal strategies are maintained during difficult periods.

#### Acceptance Criteria

1. WHEN market volatility increases, THE System SHALL maintain exposure according to regime and trend signals
2. WHEN drawdowns exceed -10%, THE System SHALL resist attempts to reduce position sizes outside of structural rules
3. WHEN external pressure mounts, THE System SHALL log interference attempts without modifying behavior
4. WHEN psychological stress peaks, THE System SHALL continue weekly evaluation cadence without acceleration
5. THE System SHALL maintain conviction mechanisms until maximum drawdown covenant is breached