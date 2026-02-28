# Requirements Document: Unified Volatility Engine

## Introduction

This document specifies the requirements for transforming the Northstar v3 options trading system into a unified institutional-grade volatility trading engine. The transformation consolidates fragmented components into a cohesive volatility organism with intelligent strategy generation, advanced risk management, and regime-adaptive behavior.

The system will move from pre-defined strategy templates to exposure-based optimization, where the engine reasons about target Greeks (Delta, Gamma, Vega, Theta) and generates optimal option structures dynamically. This represents a fundamental architectural shift toward treating volatility as a unified asset class with systematic exploitation of market inefficiencies.

## Glossary

- **Volatility_Engine**: The unified system that integrates volatility surface modeling, regime detection, strategy generation, and risk management
- **Strategy_Generator**: AST-based component that constructs option structures from target exposure specifications
- **Greeks_Aggregator**: Portfolio-level calculator for Delta, Gamma, Vega, Theta, and higher-order Greeks
- **Regime_Detector**: Component that identifies current market volatility regime (low-vol, high-vol, crisis, transition)
- **Dispersion_Module**: System for trading correlation between index volatility and constituent stock volatilities
- **Gamma_Scalper**: Engine for harvesting realized variance through delta-hedging of long gamma positions
- **Risk_Authority**: Absolute veto power component that can halt trading based on risk thresholds
- **Monte_Carlo_Engine**: Stochastic simulation system for tail risk modeling and scenario analysis
- **IV_Surface**: Implied volatility surface across strikes and expirations
- **Vol_of_Vol**: Volatility of volatility metric measuring second-order uncertainty
- **Realized_Variance**: Actual historical variance computed from price movements
- **Implied_Variance**: Forward-looking variance implied by option prices
- **Correlation_Matrix**: Time-varying correlation structure between assets
- **Greeks**: Option sensitivities (Delta, Gamma, Vega, Theta, Rho, Vanna, Volga)
- **Target_Exposure**: Desired portfolio Greeks profile specified as constraints
- **Option_Structure**: Combination of options (spreads, straddles, butterflies, etc.)
- **Regime_State**: Current market environment classification affecting strategy behavior
- **Capital_Allocator**: System that distributes capital across strategy buckets based on regime
- **Stress_Scenario**: Extreme market condition used for risk testing
- **AST**: Abstract Syntax Tree representation of option structures for programmatic generation

## Requirements

### Requirement 1: Unified Volatility State Engine

**User Story:** As a volatility trader, I want a single unified state engine that combines all volatility-related market information, so that I have one source of truth for decision-making across all strategies.

#### Acceptance Criteria

1. WHEN the system initializes, THE Volatility_Engine SHALL load and integrate equity regime, macro state, IV surface, correlation matrix, event risk calendar, and vol-of-vol metrics into a unified state object
2. WHEN any component of the volatility state updates, THE Volatility_Engine SHALL propagate the update to all dependent systems within 100ms
3. WHEN multiple data sources provide conflicting information, THE Volatility_Engine SHALL apply a deterministic resolution policy and log the conflict
4. THE Volatility_Engine SHALL maintain temporal consistency by timestamping all state updates with microsecond precision
5. WHEN queried for current state, THE Volatility_Engine SHALL return a complete snapshot including all components and their last update timestamps
6. THE Volatility_Engine SHALL persist state snapshots to disk every 5 minutes for recovery purposes
7. WHEN recovering from failure, THE Volatility_Engine SHALL restore the most recent valid state snapshot and validate data integrity

### Requirement 2: Intelligent Strategy Generator

**User Story:** As a portfolio manager, I want the system to generate option structures from target exposures rather than selecting from pre-defined strategies, so that I can express precise risk preferences and adapt to any market condition.

#### Acceptance Criteria

1. WHEN provided with target Greeks (Delta, Gamma, Vega, Theta) and constraints, THE Strategy_Generator SHALL construct an AST representation of option structures that satisfy the targets within specified tolerances
2. WHEN multiple option structures satisfy the target exposures, THE Strategy_Generator SHALL rank them by cost-efficiency and present the top 3 candidates
3. WHEN no feasible structure exists within constraints, THE Strategy_Generator SHALL return an error with the closest achievable exposure profile
4. THE Strategy_Generator SHALL support composition of basic structures (calls, puts, spreads, straddles, strangles, butterflies, condors, calendars) into complex multi-leg positions
5. WHEN generating structures, THE Strategy_Generator SHALL respect position limits, liquidity constraints, and margin requirements
6. THE Strategy_Generator SHALL validate that generated structures have positive expected value under the current regime probability distribution
7. WHEN market conditions change significantly, THE Strategy_Generator SHALL re-evaluate existing structures and suggest adjustments

### Requirement 3: Portfolio Greeks Aggregator

**User Story:** As a risk manager, I want real-time portfolio-level Greeks tracking with automatic constraint enforcement, so that I can ensure the portfolio stays within risk limits at all times.

#### Acceptance Criteria

1. WHEN any position is added or modified, THE Greeks_Aggregator SHALL recompute portfolio-level Delta, Gamma, Vega, Theta, Rho, Vanna, and Volga within 50ms
2. THE Greeks_Aggregator SHALL maintain separate Greek calculations for each underlying asset and aggregate them at the portfolio level
3. WHEN portfolio Greeks exceed predefined thresholds, THE Greeks_Aggregator SHALL trigger alerts to the Risk_Authority
4. THE Greeks_Aggregator SHALL support scenario analysis by computing Greeks under shifted market conditions (±10% spot, ±25% IV, ±1 day time decay)
5. WHEN computing Greeks, THE Greeks_Aggregator SHALL use consistent pricing models and volatility surfaces across all positions
6. THE Greeks_Aggregator SHALL track Greek evolution over time and detect anomalous changes that may indicate pricing errors
7. THE Greeks_Aggregator SHALL provide Greeks decomposition showing contribution from each position to portfolio totals

### Requirement 4: Dispersion Trading Module

**User Story:** As a volatility arbitrageur, I want to systematically exploit correlation inefficiencies between index volatility and stock volatilities, so that I can capture dispersion premium when correlation is mispriced.

#### Acceptance Criteria

1. WHEN the correlation matrix updates, THE Dispersion_Module SHALL compute the implied correlation from index options and compare it to realized correlation from constituent stocks
2. WHEN implied correlation exceeds realized correlation by more than a threshold, THE Dispersion_Module SHALL generate a dispersion trade recommendation (short index vol, long stock vol)
3. WHEN implied correlation is below realized correlation by more than a threshold, THE Dispersion_Module SHALL generate a reverse dispersion trade recommendation
4. THE Dispersion_Module SHALL weight constituent stock positions by their contribution to index variance
5. THE Dispersion_Module SHALL monitor correlation risk by tracking the spread between implied and realized correlation
6. WHEN dispersion positions are active, THE Dispersion_Module SHALL rebalance delta hedges daily to maintain market neutrality
7. THE Dispersion_Module SHALL compute expected P&L from dispersion trades based on correlation mean reversion assumptions

### Requirement 5: Gamma Scalping Engine

**User Story:** As a volatility trader, I want to systematically harvest realized variance through gamma scalping, so that I can profit when realized volatility exceeds implied volatility.

#### Acceptance Criteria

1. WHEN holding long gamma positions, THE Gamma_Scalper SHALL compute optimal delta-hedging frequency based on transaction costs and gamma exposure
2. WHEN spot price moves beyond a threshold, THE Gamma_Scalper SHALL execute delta-hedging trades to lock in gamma P&L
3. THE Gamma_Scalper SHALL track cumulative realized variance and compare it to the implied variance paid for the options
4. WHEN realized variance significantly exceeds implied variance, THE Gamma_Scalper SHALL increase hedging frequency to maximize P&L capture
5. THE Gamma_Scalper SHALL account for transaction costs, bid-ask spreads, and slippage when determining hedging thresholds
6. THE Gamma_Scalper SHALL support both continuous hedging (high frequency) and discrete hedging (threshold-based) modes
7. WHEN gamma positions approach expiration, THE Gamma_Scalper SHALL adjust hedging strategy to account for increasing gamma and theta decay

### Requirement 6: Regime-Adaptive Capital Allocator

**User Story:** As a fund manager, I want capital allocation to adapt dynamically based on the current volatility regime, so that I deploy more capital to strategies that perform well in the current environment.

#### Acceptance Criteria

1. WHEN the Regime_Detector identifies a regime change, THE Capital_Allocator SHALL recompute optimal capital allocation across strategy buckets (dispersion, gamma scalping, directional vol, relative value)
2. THE Capital_Allocator SHALL maintain historical performance statistics for each strategy bucket within each regime
3. WHEN allocating capital, THE Capital_Allocator SHALL apply Kelly criterion with fractional sizing to balance growth and risk
4. THE Capital_Allocator SHALL enforce minimum and maximum allocation constraints for each strategy bucket to maintain diversification
5. WHEN a strategy bucket experiences drawdown exceeding a threshold, THE Capital_Allocator SHALL reduce its allocation until performance recovers
6. THE Capital_Allocator SHALL support regime-conditional constraints (e.g., zero allocation to short vol strategies during crisis regimes)
7. WHEN market conditions are uncertain, THE Capital_Allocator SHALL increase allocation to market-neutral strategies and reduce directional exposure

### Requirement 7: Monte Carlo Risk Engine

**User Story:** As a chief risk officer, I want comprehensive stochastic simulation of portfolio outcomes under extreme scenarios, so that I can quantify tail risk and ensure the fund can survive black swan events.

#### Acceptance Criteria

1. WHEN performing risk analysis, THE Monte_Carlo_Engine SHALL simulate 10,000 paths of underlying prices, volatilities, and correlations over the portfolio horizon
2. THE Monte_Carlo_Engine SHALL incorporate fat-tailed distributions and volatility clustering to capture realistic market dynamics
3. WHEN simulating crisis scenarios, THE Monte_Carlo_Engine SHALL model correlation breakdown where correlations spike toward 1.0
4. THE Monte_Carlo_Engine SHALL compute Value-at-Risk (VaR) and Conditional Value-at-Risk (CVaR) at 95%, 99%, and 99.9% confidence levels
5. THE Monte_Carlo_Engine SHALL identify the worst-case scenarios from simulations and analyze what market conditions lead to maximum losses
6. THE Monte_Carlo_Engine SHALL validate that the portfolio can survive a combined 2008 + 2020 stress scenario without exceeding maximum drawdown limits
7. WHEN risk metrics exceed thresholds, THE Monte_Carlo_Engine SHALL trigger alerts to the Risk_Authority with detailed scenario breakdowns

### Requirement 8: Absolute Risk Authority

**User Story:** As a compliance officer, I want an independent risk authority with absolute veto power over all trading decisions, so that the system cannot violate risk limits under any circumstances.

#### Acceptance Criteria

1. THE Risk_Authority SHALL validate every proposed trade against position limits, concentration limits, Greeks limits, and margin requirements before execution
2. WHEN any risk limit is breached, THE Risk_Authority SHALL reject the trade and log the violation with full context
3. THE Risk_Authority SHALL have the power to force-close positions when portfolio risk exceeds emergency thresholds
4. WHEN market conditions deteriorate rapidly, THE Risk_Authority SHALL activate emergency protocols including position size reduction and hedging requirements
5. THE Risk_Authority SHALL operate independently from the Strategy_Generator and Capital_Allocator to prevent conflicts of interest
6. THE Risk_Authority SHALL maintain an audit trail of all risk decisions including approvals, rejections, and emergency actions
7. WHEN the Risk_Authority detects systematic risk limit violations, THE Risk_Authority SHALL escalate to human oversight and halt automated trading

### Requirement 9: Regime Detection and Classification

**User Story:** As a systematic trader, I want accurate real-time regime detection that classifies market conditions, so that strategies can adapt their behavior to the current environment.

#### Acceptance Criteria

1. THE Regime_Detector SHALL classify the current market into one of four regimes: low-volatility, high-volatility, crisis, or transition
2. WHEN computing regime classification, THE Regime_Detector SHALL consider VIX level, VIX term structure, realized volatility, correlation, and market breadth
3. THE Regime_Detector SHALL use a probabilistic model that outputs regime probabilities rather than hard classifications
4. WHEN regime probabilities are ambiguous (no regime above 60% probability), THE Regime_Detector SHALL flag the state as uncertain and recommend defensive positioning
5. THE Regime_Detector SHALL detect regime transitions by monitoring the rate of change in regime probabilities
6. THE Regime_Detector SHALL maintain a regime history log showing regime classifications and transition timestamps
7. WHEN a regime persists for an unusually long duration, THE Regime_Detector SHALL increase monitoring for potential regime exhaustion

### Requirement 10: Volatility Surface Modeling

**User Story:** As a derivatives trader, I want accurate implied volatility surface modeling across all strikes and expirations, so that I can identify mispriced options and arbitrage opportunities.

#### Acceptance Criteria

1. WHEN option market data updates, THE IV_Surface SHALL fit a smooth volatility surface using SVI (Stochastic Volatility Inspired) or SABR parameterization
2. THE IV_Surface SHALL enforce no-arbitrage constraints including calendar spread arbitrage and butterfly arbitrage
3. WHEN the surface fit fails quality checks, THE IV_Surface SHALL fall back to a simpler model and alert operators
4. THE IV_Surface SHALL extrapolate volatility for strikes and expirations where market quotes are unavailable
5. THE IV_Surface SHALL compute local volatility and implied probability distributions from the fitted surface
6. THE IV_Surface SHALL detect and flag anomalous quotes that deviate significantly from the fitted surface
7. WHEN pricing options, THE IV_Surface SHALL provide interpolated volatility with confidence intervals based on fit quality

### Requirement 11: System Cleanup and Consolidation

**User Story:** As a system architect, I want to identify and remove obsolete code while consolidating duplicate functionality, so that the codebase is maintainable and the architecture is clean.

#### Acceptance Criteria

1. WHEN analyzing the codebase, THE System SHALL identify components that are no longer referenced or have been superseded by newer implementations
2. THE System SHALL detect duplicate functionality across modules (e.g., multiple dashboard implementations, multiple regime detectors) and recommend consolidation
3. WHEN removing obsolete code, THE System SHALL archive it to a separate directory with documentation explaining why it was deprecated
4. THE System SHALL consolidate multiple state managers (unified_state_manager in cohesion/, state/, and core/) into a single authoritative implementation
5. THE System SHALL merge redundant risk components (risk_engine in cohesion/, processing/, and risk/) into the unified Risk_Authority
6. THE System SHALL eliminate circular dependencies and establish clear module boundaries with defined interfaces
7. WHEN consolidation is complete, THE System SHALL generate a migration guide documenting what changed and how to update dependent code

### Requirement 12: Production-Grade Execution Integration

**User Story:** As a trader, I want seamless integration with production execution systems, so that generated strategies can be executed in live markets with proper order management and risk controls.

#### Acceptance Criteria

1. WHEN a strategy is approved for execution, THE Volatility_Engine SHALL generate execution instructions including order type, limit prices, and time-in-force parameters
2. THE Volatility_Engine SHALL support multiple execution venues and route orders based on liquidity and pricing
3. WHEN submitting orders, THE Volatility_Engine SHALL implement pre-trade risk checks including position limits and margin requirements
4. THE Volatility_Engine SHALL track order status (pending, filled, partially filled, rejected, cancelled) and update portfolio state accordingly
5. WHEN orders are filled, THE Volatility_Engine SHALL compute actual execution prices and slippage relative to theoretical prices
6. THE Volatility_Engine SHALL support order modification and cancellation with proper state management
7. WHEN execution fails or is rejected, THE Volatility_Engine SHALL log the failure reason and notify the Risk_Authority

### Requirement 13: Comprehensive Testing and Validation

**User Story:** As a quantitative developer, I want extensive property-based testing and stress testing, so that I can have confidence the system behaves correctly under all market conditions.

#### Acceptance Criteria

1. THE System SHALL include property-based tests for Greeks calculations that verify put-call parity, monotonicity, and boundary conditions across randomly generated option parameters
2. THE System SHALL include stress tests that replay 2008 financial crisis and 2020 COVID crash scenarios and verify the system survives without breaching risk limits
3. THE System SHALL include regime transition tests that verify strategy behavior remains stable when regimes change rapidly
4. THE System SHALL include Monte Carlo validation tests that verify simulated P&L distributions match theoretical expectations
5. THE System SHALL include integration tests that verify the complete flow from market data ingestion through strategy generation to execution
6. THE System SHALL include round-trip tests for state serialization ensuring state can be saved and restored without data loss
7. WHEN any test fails, THE System SHALL provide detailed diagnostics including input parameters, expected output, actual output, and stack traces

### Requirement 14: Real-Time Performance Monitoring

**User Story:** As a portfolio manager, I want real-time monitoring of strategy performance with attribution to specific factors, so that I can understand what is driving P&L and make informed decisions.

#### Acceptance Criteria

1. THE Volatility_Engine SHALL compute real-time P&L decomposition into Greeks contributions (Delta P&L, Gamma P&L, Vega P&L, Theta P&L)
2. THE Volatility_Engine SHALL track realized vs implied volatility for each position and compute variance P&L
3. WHEN computing performance attribution, THE Volatility_Engine SHALL separate alpha (strategy skill) from beta (market exposure)
4. THE Volatility_Engine SHALL maintain performance statistics including Sharpe ratio, Sortino ratio, maximum drawdown, and win rate
5. THE Volatility_Engine SHALL detect performance degradation by comparing recent returns to historical averages
6. THE Volatility_Engine SHALL provide regime-conditional performance analysis showing how strategies perform in each regime
7. WHEN performance metrics deteriorate significantly, THE Volatility_Engine SHALL alert operators and recommend diagnostic actions

### Requirement 15: Configuration and Parameter Management

**User Story:** As a system operator, I want centralized configuration management with validation and versioning, so that I can safely adjust system parameters without breaking functionality.

#### Acceptance Criteria

1. THE Volatility_Engine SHALL load all configuration parameters from a centralized configuration file with schema validation
2. WHEN configuration parameters are modified, THE Volatility_Engine SHALL validate that new values are within acceptable ranges before applying them
3. THE Volatility_Engine SHALL support hot-reloading of configuration parameters without requiring system restart for non-critical parameters
4. THE Volatility_Engine SHALL maintain a version history of configuration changes with timestamps and operator identifiers
5. WHEN invalid configuration is detected, THE Volatility_Engine SHALL reject the changes and continue operating with the previous valid configuration
6. THE Volatility_Engine SHALL provide configuration templates for different operating modes (aggressive, moderate, conservative)
7. THE Volatility_Engine SHALL document all configuration parameters with descriptions, valid ranges, and default values
