# Requirements Document

## Introduction

This specification addresses critical system integrity issues discovered in the Northstar V3 trading system. The system currently exhibits inconsistent state management, unreliable exposure calculations, and disconnected health metrics that prevent accurate assessment of system behavior during market stress events.

## Glossary

- **System**: The Northstar V3 trading system
- **Market_Brain**: Component responsible for market regime detection and risk assessment
- **Portfolio_Governor**: Component responsible for position sizing and portfolio construction
- **Unified_State_Manager**: Component responsible for maintaining consistent system state
- **Exposure**: The percentage of capital allocated to market positions (0-100%)
- **Market_State**: The canonical source of truth for current market conditions
- **Health_Metric**: A quantitative measure of system operational integrity

## Requirements

### Requirement 1: Single Source of Truth for Market State

**User Story:** As a system operator, I want a single authoritative source for market state, so that all components operate on consistent data.

#### Acceptance Criteria

1. THE System SHALL maintain market state in exactly one canonical location at `data/processed/market_state.parquet`
2. WHEN any component needs market state, THE System SHALL read from the canonical market state file
3. THE Market_State file SHALL contain only: date, regime, risk_on, allowed_exposure, stress_score
4. WHEN market state is updated, THE System SHALL write to the canonical location atomically
5. THE System SHALL NOT maintain duplicate or competing market state representations

### Requirement 2: Exposure Calculation Bounds

**User Story:** As a risk manager, I want exposure values to be mathematically valid, so that the system cannot enter nonsensical states.

#### Acceptance Criteria

1. WHEN calculating allowed exposure, THE System SHALL enforce a minimum bound of 0.0
2. WHEN calculating allowed exposure, THE System SHALL enforce a maximum bound of 1.0
3. IF a calculation produces NaN, THE System SHALL replace it with 0.0
4. IF a calculation produces infinity, THE System SHALL replace it with 1.0
5. THE System SHALL log any bound violations for diagnostic purposes

### Requirement 3: Meaningful System Health Metric

**User Story:** As a system operator, I want health metrics to reflect actual system state, so that I can trust operational dashboards.

#### Acceptance Criteria

1. THE System SHALL calculate health as a weighted combination of data_freshness (40%), market_consistency (30%), and portfolio_stability (30%)
2. WHEN data is stale beyond threshold, THE System SHALL reduce data_freshness score proportionally
3. WHEN market state contradicts portfolio state, THE System SHALL reduce market_consistency score
4. WHEN portfolio exhibits excessive volatility, THE System SHALL reduce portfolio_stability score
5. IF any component score is zero, THE System SHALL report overall health below 50%

### Requirement 4: Unified State Consistency

**User Story:** As a system architect, I want the unified state manager to mirror reality, so that state queries return accurate information.

#### Acceptance Criteria

1. THE Unified_State_Manager SHALL read from canonical data files: market_state.parquet, portfolio_weights.parquet, risk_state.parquet
2. WHEN queried, THE Unified_State_Manager SHALL return current values from canonical files
3. THE Unified_State_Manager SHALL NOT recompute or override canonical state values
4. WHEN canonical files are missing, THE Unified_State_Manager SHALL return error state
5. THE Unified_State_Manager SHALL validate consistency between related state values

### Requirement 5: Portfolio Governor Exposure Alignment

**User Story:** As a risk manager, I want portfolio exposure to respect market brain limits, so that the system protects capital during stress.

#### Acceptance Criteria

1. WHEN constructing a portfolio, THE Portfolio_Governor SHALL read allowed_exposure from Market_State
2. THE Portfolio_Governor SHALL calculate risk_scaled_exposure based on current portfolio risk
3. THE Portfolio_Governor SHALL set final_exposure to the minimum of allowed_exposure and risk_scaled_exposure
4. THE Portfolio_Governor SHALL NOT override exposure limits with hardcoded values
5. WHEN exposure limits change, THE Portfolio_Governor SHALL adjust positions accordingly

### Requirement 6: State Transition Logging

**User Story:** As a system operator, I want detailed logs of state transitions, so that I can diagnose inconsistencies.

#### Acceptance Criteria

1. WHEN market state changes, THE System SHALL log previous and new values with timestamp
2. WHEN exposure calculations produce bounded values, THE System SHALL log the original unbounded value
3. WHEN health metrics change significantly (>10%), THE System SHALL log contributing factors
4. WHEN state inconsistencies are detected, THE System SHALL log all conflicting values
5. THE System SHALL maintain state transition logs for at least 90 days

### Requirement 7: Exposure History Tracking

**User Story:** As a quantitative analyst, I want historical exposure data, so that I can validate system behavior over time.

#### Acceptance Criteria

1. THE System SHALL maintain a time series of allowed_exposure in `data/processed/exposure_history.parquet`
2. THE System SHALL maintain a time series of actual_exposure in `data/processed/exposure_history.parquet`
3. WHEN exposure is calculated, THE System SHALL append to exposure history
4. THE System SHALL retain exposure history for at least 365 days
5. THE System SHALL provide utilities to compare allowed vs actual exposure over time

### Requirement 8: Drawdown Calculation and Tracking

**User Story:** As a portfolio manager, I want accurate drawdown metrics, so that I can assess system performance during stress.

#### Acceptance Criteria

1. THE System SHALL calculate portfolio drawdown as percentage decline from peak equity
2. THE System SHALL calculate benchmark drawdown using the same methodology
3. THE System SHALL store drawdown metrics in `data/processed/portfolio_analytics.json`
4. WHEN calculating drawdown, THE System SHALL use point-in-time equity values
5. THE System SHALL update drawdown metrics daily during market hours

### Requirement 9: State Validation on Startup

**User Story:** As a system operator, I want state validation on startup, so that I detect corruption before trading begins.

#### Acceptance Criteria

1. WHEN the system starts, THE System SHALL validate all canonical state files exist
2. WHEN the system starts, THE System SHALL validate state file schemas match expected format
3. WHEN the system starts, THE System SHALL validate cross-file consistency (e.g., dates align)
4. IF validation fails, THE System SHALL refuse to start and log specific failures
5. THE System SHALL provide a repair utility for common state corruption patterns

### Requirement 10: Atomic State Updates

**User Story:** As a system architect, I want atomic state updates, so that partial writes cannot corrupt system state.

#### Acceptance Criteria

1. WHEN writing state files, THE System SHALL write to temporary files first
2. WHEN temporary write completes, THE System SHALL atomically rename to canonical location
3. IF a write fails, THE System SHALL leave previous state intact
4. THE System SHALL use file locking to prevent concurrent writes
5. THE System SHALL validate written data before committing the atomic rename
