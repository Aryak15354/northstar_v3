# Implementation Plan: Unified Volatility Engine

## Overview

This implementation plan transforms the Northstar v3 options trading system into a unified institutional-grade volatility trading engine. The plan follows a systematic approach:

1. **Phase 1: System Cleanup** - Identify and consolidate duplicate components
2. **Phase 2: Core Infrastructure** - Build unified state engine and foundational components
3. **Phase 3: Strategy & Risk** - Implement AST-based strategy generation and risk management
4. **Phase 4: Advanced Modules** - Build dispersion, gamma scalping, and regime-adaptive systems
5. **Phase 5: Integration & Testing** - Wire everything together with comprehensive testing

The implementation prioritizes establishing clean module boundaries and eliminating redundancy before building new functionality.

## Tasks

### Phase 1: System Cleanup and Consolidation

- [x] 1. Analyze and document current system architecture
  - Scan all files in src/ to create component inventory
  - Identify all state managers, risk engines, regime detectors, and dashboard implementations
  - Document dependencies and data flows between components
  - Create architecture diagram showing current state
  - _Requirements: 11.1, 11.2_

- [x] 2. Consolidate state management components
  - [x] 2.1 Identify authoritative state manager implementation
    - Compare src/cohesion/unified_state_manager.py, src/state/unified_state_manager.py, and src/core/ implementations
    - Evaluate completeness, test coverage, and integration points
    - Select single authoritative implementation
    - _Requirements: 11.4_
  
  - [x] 2.2 Create unified state manager in src/volatility/state_engine.py
    - Implement VolatilityState dataclass with all required fields
    - Implement VolatilityStateEngine with update methods for IV surface, regime, correlations
    - Add state persistence (save/restore snapshots)
    - Add state validation and consistency checks
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7_
  
  - [x] 2.3 Archive obsolete state managers
    - Move deprecated implementations to archive/deprecated/state_managers/
    - Create migration guide documenting changes
    - Update all imports to point to new unified state manager
    - _Requirements: 11.3, 11.7_


- [x] 3. Consolidate risk management components
  - [x] 3.1 Merge risk engines into unified Risk Authority
    - Analyze src/cohesion/risk_engine.py, src/processing/risk_engine.py, src/risk/unified_risk_coordinator.py
    - Extract best functionality from each implementation
    - Create src/volatility/risk_authority.py with absolute veto power
    - Implement trade validation, emergency actions, and audit trail
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7_
  
  - [x] 3.2 Archive obsolete risk components
    - Move deprecated risk engines to archive/deprecated/risk/
    - Update all risk-related imports
    - Document risk authority interface and usage
    - _Requirements: 11.3, 11.7_

- [x] 4. Consolidate regime detection components
  - [x] 4.1 Unify regime detectors
    - Analyze src/processing/market_regime.py, src/processing/options_regime.py, src/options/regime_detector.py, src/intelligence/regime_aware_specialists.py
    - Create single authoritative src/volatility/regime_detector.py
    - Implement probabilistic regime classification (low-vol, high-vol, crisis, transition)
    - Add regime history tracking and transition detection
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7_
  
  - [x] 4.2 Archive obsolete regime detectors
    - Move deprecated implementations to archive/deprecated/regime/
    - Update imports across codebase
    - _Requirements: 11.3, 11.7_

- [x] 5. Consolidate dashboard implementations
  - [x] 5.1 Select production dashboard
    - Evaluate all dashboard files in src/dashboard/
    - Identify most complete and production-ready implementation
    - Archive all other dashboard variants
    - _Requirements: 11.2, 11.3_
  
  - [x] 5.2 Integrate dashboard with unified volatility engine
    - Update dashboard to consume VolatilityState
    - Add real-time Greeks monitoring display
    - Add regime visualization and performance attribution
    - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5, 14.6, 14.7_

- [x] 6. Consolidate volatility processing components
  - [x] 6.1 Merge volatility engines
    - Analyze src/processing/volatility_engine.py and src/processing/options_volatility.py
    - Extract IV surface fitting logic
    - Integrate into unified VolatilityStateEngine
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7_
  
  - [x] 6.2 Archive obsolete volatility components
    - Move deprecated implementations to archive/deprecated/volatility/
    - Update imports
    - _Requirements: 11.3_

- [x] 7. Consolidate intelligence engines
  - [x] 7.1 Merge intelligence components
    - Analyze src/intelligence/unified_intelligence_engine.py, backup version, and src/cohesion/intelligence_engine.py
    - Identify unique functionality in each
    - Create consolidated intelligence layer that integrates with volatility engine
    - _Requirements: 11.2, 11.4, 11.5_
  
  - [x] 7.2 Archive obsolete intelligence engines
    - Move deprecated implementations to archive/deprecated/intelligence/
    - Update imports
    - _Requirements: 11.3, 11.7_

- [x] 8. Checkpoint - System cleanup complete
  - Verify all duplicate components archived
  - Verify all imports updated to use unified components
  - Run existing tests to ensure no regressions
  - Document consolidated architecture
  - Ensure all tests pass, ask the user if questions arise.


### Phase 2: Core Infrastructure

- [x] 9. Implement IV Surface modeling
  - [x] 9.1 Create IVSurface class with SVI parameterization
    - Implement src/volatility/iv_surface.py
    - Add SVI/SABR fitting algorithms
    - Implement no-arbitrage constraint enforcement
    - Add surface quality metrics and validation
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7_
  
  - [x] 9.2 Write property tests for IV surface
    - **Property 1: No-arbitrage constraints**
    - *For any* fitted IV surface, calendar spreads and butterfly spreads should have non-negative prices
    - **Validates: Requirements 10.2**
  
  - [x] 9.3 Write unit tests for IV surface edge cases
    - Test surface fitting with sparse data
    - Test extrapolation behavior at extreme strikes
    - Test fallback to simpler models when fit fails
    - _Requirements: 10.3, 10.4_

- [x] 10. Implement Portfolio Greeks Aggregator
  - [x] 10.1 Create Greeks calculation engine
    - Implement src/volatility/greeks_aggregator.py
    - Add Black-Scholes Greeks formulas (Delta, Gamma, Vega, Theta, Rho)
    - Add second-order Greeks (Vanna, Volga, Charm, Vomma)
    - Implement portfolio-level aggregation with per-underlying breakdown
    - _Requirements: 3.1, 3.2, 3.5, 3.7_
  
  - [x] 10.2 Add Greeks constraint checking
    - Implement constraint validation against limits
    - Add scenario analysis (shifted spot, IV, time)
    - Add anomaly detection for Greek evolution
    - _Requirements: 3.3, 3.4, 3.6_
  
  - [x] 10.3 Write property tests for Greeks calculations
    - **Property 2: Put-call parity**
    - *For any* strike and expiry, call_price - put_price should equal spot - strike * discount_factor
    - **Validates: Requirements 13.1**
  
  - [x] 10.4 Write property tests for Greeks monotonicity
    - **Property 3: Delta monotonicity**
    - *For any* option, increasing spot price should increase call delta and decrease put delta (in absolute value)
    - **Validates: Requirements 13.1**
  
  - [x] 10.5 Write property tests for Greeks boundary conditions
    - **Property 4: Greeks at expiry**
    - *For any* option at expiry, delta should be 0 or 1 for calls (0 or -1 for puts), and gamma/vega should be 0
    - **Validates: Requirements 13.1**

- [x] 11. Implement Configuration Management
  - [x] 11.1 Create centralized configuration system
    - Implement src/volatility/config.py with schema validation
    - Add configuration templates (aggressive, moderate, conservative)
    - Implement hot-reloading for non-critical parameters
    - Add configuration versioning and audit trail
    - _Requirements: 15.1, 15.2, 15.3, 15.4, 15.5, 15.6, 15.7_
  
  - [x] 11.2 Write unit tests for configuration validation
    - Test parameter range validation
    - Test invalid configuration rejection
    - Test configuration versioning
    - _Requirements: 15.2, 15.5_

- [x] 12. Implement State Persistence
  - [x] 12.1 Add state serialization
    - Implement save_state and load_state methods
    - Add JSON serialization for all state components
    - Implement automatic snapshot every 5 minutes
    - Add state validation on restore
    - _Requirements: 1.6, 1.7_
  
  - [x] 12.2 Write property tests for state round-trip
    - **Property 5: State serialization round-trip**
    - *For any* valid VolatilityState, serializing then deserializing should produce an equivalent state
    - **Validates: Requirements 13.6**

- [x] 13. Checkpoint - Core infrastructure complete
  - Verify IV surface fitting works with real option data
  - Verify Greeks calculations match theoretical values
  - Verify state persistence and recovery
  - Ensure all tests pass, ask the user if questions arise.


### Phase 3: Strategy Generation and Risk Management

- [x] 14. Implement AST-based Strategy Generator
  - [x] 14.1 Create option structure AST nodes
    - Implement src/volatility/strategy_ast.py with OptionNode base class
    - Add primitive nodes (Call, Put, Spread, Straddle, Strangle, Butterfly, Condor, Calendar)
    - Add composite nodes for complex structures
    - _Requirements: 2.4_
  
  - [x] 14.2 Implement strategy generation algorithm
    - Create src/volatility/strategy_generator.py
    - Implement target Greeks decomposition
    - Implement structure generation from primitives
    - Add pricing and Greeks computation for structures
    - Implement ranking by cost-efficiency
    - _Requirements: 2.1, 2.2, 2.3, 2.5, 2.6, 2.7_
  
  - [x] 14.3 Add structure composition logic
    - Implement AST composition for complex multi-leg positions
    - Add no-arbitrage validation for composed structures
    - _Requirements: 2.4_
  
  - [x] 14.4 Write property tests for strategy generation
    - **Property 6: Generated structures satisfy target Greeks**
    - *For any* target Greeks specification within feasible bounds, generated structures should have actual Greeks within specified tolerances
    - **Validates: Requirements 2.1**
  
  - [x] 14.5 Write property tests for structure composition
    - **Property 7: Composed Greeks are additive**
    - *For any* two option structures, the Greeks of the composed structure should equal the sum of individual Greeks
    - **Validates: Requirements 2.4**
  
  - [x] 14.6 Write unit tests for strategy generation edge cases
    - Test generation with infeasible target Greeks
    - Test generation with tight constraints
    - Test ranking with multiple equivalent structures
    - _Requirements: 2.3, 2.5_

- [x] 15. Implement Risk Authority
  - [x] 15.1 Create trade validation system
    - Implement src/volatility/risk_authority.py
    - Add validation for position limits, Greeks limits, concentration limits
    - Add margin requirement checks
    - Add liquidity validation
    - _Requirements: 8.1, 8.2_
  
  - [x] 15.2 Implement emergency action system
    - Add emergency trigger detection
    - Implement emergency actions (reduce positions, liquidate, hedge, halt)
    - Add position selection for liquidation
    - _Requirements: 8.3, 8.4_
  
  - [x] 15.3 Add regime-conditional limits
    - Implement regime-specific risk limits
    - Add automatic limit adjustment on regime changes
    - _Requirements: 8.1_
  
  - [x] 15.4 Implement audit trail
    - Add logging for all risk decisions
    - Track approvals, rejections, and emergency actions
    - Implement escalation to human oversight
    - _Requirements: 8.6, 8.7_
  
  - [x] 15.5 Write property tests for risk validation
    - **Property 8: Risk authority rejects limit violations**
    - *For any* proposed trade that would breach risk limits, the Risk Authority should reject it
    - **Validates: Requirements 8.1, 8.2**
  
  - [x] 15.6 Write unit tests for emergency actions
    - Test emergency triggers and responses
    - Test position liquidation selection
    - Test audit trail completeness
    - _Requirements: 8.3, 8.4, 8.6_

- [x] 16. Checkpoint - Strategy and risk systems operational
  - Verify strategy generator produces valid structures
  - Verify risk authority correctly validates trades
  - Test emergency action triggers
  - Ensure all tests pass, ask the user if questions arise.


### Phase 4: Advanced Trading Modules

- [x] 17. Implement Dispersion Trading Module
  - [x] 17.1 Create dispersion analysis engine
    - Implement src/volatility/dispersion_module.py
    - Add implied correlation computation from index options
    - Add realized correlation computation from constituent stocks
    - Implement dispersion opportunity detection
    - _Requirements: 4.1, 4.2, 4.3_
  
  - [x] 17.2 Implement variance weighting
    - Add index weight loading
    - Implement variance contribution calculation
    - Create variance-weighted position sizing
    - _Requirements: 4.4_
  
  - [x] 17.3 Add dispersion position management
    - Implement delta-hedging for dispersion positions
    - Add daily rebalancing logic
    - Implement correlation risk monitoring
    - Add expected P&L calculation
    - _Requirements: 4.5, 4.6, 4.7_
  
  - [x] 17.4 Write property tests for dispersion trading
    - **Property 9: Dispersion positions are delta-neutral**
    - *For any* dispersion trade after rebalancing, portfolio delta should be within neutrality threshold
    - **Validates: Requirements 4.6**
  
  - [x]* 17.5 Write unit tests for dispersion edge cases
    - Test with extreme correlation spreads
    - Test with missing constituent data
    - Test rebalancing threshold logic
    - _Requirements: 4.1, 4.2, 4.3_

- [x] 18. Implement Gamma Scalping Engine
  - [x] 18.1 Create gamma scalping core
    - Implement src/volatility/gamma_scalper.py
    - Add optimal hedging threshold calculation
    - Implement hedge trigger detection
    - Add hedge order generation
    - _Requirements: 5.1, 5.2, 5.5_
  
  - [x] 18.2 Add realized variance tracking
    - Implement realized variance computation from hedge history
    - Add comparison to implied variance
    - Track cumulative gamma P&L
    - _Requirements: 5.3, 5.4_
  
  - [x] 18.3 Implement adaptive hedging
    - Add hedging frequency adaptation based on realized vs implied variance
    - Support continuous and discrete hedging modes
    - Add expiration-aware hedging adjustments
    - _Requirements: 5.4, 5.6, 5.7_
  
  - [x] 18.4 Write property tests for gamma scalping
    - **Property 10: Hedging reduces delta exposure**
    - *For any* long gamma position, executing a hedge should reduce absolute delta toward zero
    - **Validates: Requirements 5.2**
  
  - [x] 18.5 Write property tests for realized variance
    - **Property 11: Realized variance is non-negative**
    - *For any* sequence of hedges, computed realized variance should be non-negative
    - **Validates: Requirements 5.3**
  
  - [x] 18.6 Write unit tests for gamma scalping edge cases
    - Test hedging near expiration
    - Test with extreme volatility
    - Test transaction cost impact
    - _Requirements: 5.5, 5.7_

- [x] 19. Implement Regime-Adaptive Capital Allocator
  - [x] 19.1 Create capital allocation engine
    - Implement src/volatility/capital_allocator.py
    - Add regime-based allocation computation
    - Implement Kelly criterion with fractional sizing
    - Add historical performance tracking by regime
    - _Requirements: 6.1, 6.2, 6.3_
  
  - [x] 19.2 Add allocation constraints
    - Implement min/max allocation bounds
    - Add regime-conditional constraints (e.g., zero short vol in crisis)
    - Implement diversification requirements
    - _Requirements: 6.4, 6.6, 6.7_
  
  - [x] 19.3 Implement drawdown-based adjustment
    - Add drawdown tracking per strategy bucket
    - Implement allocation reduction for strategies in drawdown
    - Add recovery detection and allocation restoration
    - _Requirements: 6.5_
  
  - [x] 19.4 Write property tests for capital allocation
    - **Property 12: Allocations sum to total capital**
    - *For any* capital allocation result, the sum of all strategy allocations should equal total available capital
    - **Validates: Requirements 6.1**
  
  - [x] 19.5 Write property tests for allocation constraints
    - **Property 13: Allocations respect bounds**
    - *For any* strategy bucket, allocated capital should be between min and max bounds
    - **Validates: Requirements 6.4**
  
  - [x] 19.6 Write unit tests for regime-conditional allocation
    - Test crisis regime constraints (zero short vol)
    - Test low-vol regime preferences
    - Test transition regime defensive positioning
    - _Requirements: 6.6, 6.7_

- [x] 20. Checkpoint - Advanced modules operational
  - Verify dispersion module detects opportunities
  - Verify gamma scalper generates appropriate hedges
  - Verify capital allocator adapts to regime changes
  - Ensure all tests pass, ask the user if questions arise.


### Phase 5: Monte Carlo Risk Engine and Stress Testing

- [x] 21. Implement Monte Carlo simulation framework
  - [x] 21.1 Create price path generator
    - Implement src/volatility/monte_carlo_engine.py
    - Add correlated price path generation with fat-tailed distributions
    - Implement Student-t innovations for realistic tail behavior
    - Add correlation matrix integration
    - _Requirements: 7.1, 7.2_
  
  - [x] 21.2 Implement stochastic volatility paths
    - Add Heston model for volatility dynamics
    - Implement vol-of-vol modeling
    - Add volatility clustering effects
    - _Requirements: 7.1, 7.2_
  
  - [x] 21.3 Add portfolio simulation
    - Implement portfolio revaluation along simulated paths
    - Add Greeks evolution tracking
    - Compute P&L distributions
    - _Requirements: 7.1_
  
  - [x] 21.4 Write property tests for Monte Carlo simulation
    - **Property 14: Simulated paths have correct mean**
    - *For any* large number of simulated price paths, the average terminal price should converge to the forward price
    - **Validates: Requirements 13.4**
  
  - [x] 21.5 Write property tests for volatility paths
    - **Property 15: Volatility paths are non-negative**
    - *For any* simulated volatility path, all volatility values should be non-negative
    - **Validates: Requirements 7.1**

- [x] 22. Implement risk metrics computation
  - [x] 22.1 Add VaR and CVaR calculation
    - Implement Value-at-Risk at 95%, 99%, 99.9% confidence levels
    - Implement Conditional Value-at-Risk (expected shortfall)
    - Add maximum drawdown computation across paths
    - _Requirements: 7.4_
  
  - [x] 22.2 Add scenario analysis
    - Implement worst-case scenario identification
    - Add scenario decomposition (what market conditions cause max loss)
    - Compute probability of ruin
    - _Requirements: 7.5_
  
  - [x] 22.3 Implement risk alerting
    - Add threshold monitoring for risk metrics
    - Implement alerts to Risk Authority when thresholds breached
    - Add detailed scenario breakdowns in alerts
    - _Requirements: 7.7_
  
  - [x] 22.4 Write unit tests for risk metrics
    - Test VaR calculation accuracy
    - Test CVaR computation
    - Test maximum drawdown detection
    - _Requirements: 7.4_

- [x] 23. Implement stress testing framework
  - [x] 23.1 Create stress scenario definitions
    - Implement crisis scenario modeling (2008 + 2020 combined)
    - Add correlation breakdown scenarios
    - Add volatility spike scenarios
    - Add liquidity crisis scenarios
    - _Requirements: 7.3, 7.6_
  
  - [x] 23.2 Implement stress test execution
    - Add portfolio revaluation under stress scenarios
    - Compute stress P&L and survival checks
    - Validate portfolio can survive maximum drawdown limits
    - _Requirements: 7.6_
  
  - [x] 23.3 Write property tests for stress testing
    - **Property 16: Portfolio survives stress scenarios**
    - *For any* portfolio configuration, stress test P&L should not exceed maximum loss threshold
    - **Validates: Requirements 7.6**
  
  - [x] 23.4 Write integration tests for stress scenarios
    - Test 2008 financial crisis scenario
    - Test 2020 COVID crash scenario
    - Test combined crisis scenario
    - _Requirements: 13.2_

- [x] 24. Checkpoint - Risk engine complete
  - Verify Monte Carlo simulations produce realistic distributions
  - Verify risk metrics calculated correctly
  - Verify stress tests identify vulnerabilities
  - Ensure all tests pass, ask the user if questions arise.


### Phase 6: Execution Integration and Performance Monitoring

- [x] 25. Implement execution interface
  - [x] 25.1 Create execution instruction generator
    - Implement src/volatility/execution_interface.py
    - Add order generation from approved strategies
    - Implement order type selection (market, limit, stop)
    - Add time-in-force parameter handling
    - _Requirements: 12.1_
  
  - [x] 25.2 Add multi-venue routing
    - Implement venue selection based on liquidity and pricing
    - Add order routing logic
    - _Requirements: 12.2_
  
  - [x] 25.3 Implement pre-trade risk checks
    - Add position limit validation before order submission
    - Add margin requirement checks
    - Integrate with Risk Authority for approval
    - _Requirements: 12.3_
  
  - [x] 25.4 Add order status tracking
    - Implement order state management (pending, filled, rejected, cancelled)
    - Add portfolio state updates on fills
    - Track execution prices and slippage
    - _Requirements: 12.4, 12.5_
  
  - [x] 25.5 Implement order modification and cancellation
    - Add order modification logic with state management
    - Add cancellation handling
    - Implement failure logging and notification
    - _Requirements: 12.6, 12.7_
  
  - [x] 25.6 Write integration tests for execution flow
    - Test complete flow from strategy approval to execution
    - Test order rejection handling
    - Test partial fill scenarios
    - _Requirements: 13.5_

- [x] 26. Implement performance monitoring and attribution
  - [x] 26.1 Create real-time P&L tracking
    - Implement src/volatility/performance_monitor.py
    - Add real-time P&L decomposition into Greeks contributions
    - Track realized vs implied volatility per position
    - Compute variance P&L
    - _Requirements: 14.1, 14.2_
  
  - [x] 26.2 Add performance attribution
    - Separate alpha (strategy skill) from beta (market exposure)
    - Implement regime-conditional performance analysis
    - Track performance statistics (Sharpe, Sortino, max drawdown, win rate)
    - _Requirements: 14.3, 14.4, 14.6_
  
  - [x] 26.3 Implement performance degradation detection
    - Add comparison of recent returns to historical averages
    - Implement alerting when performance deteriorates
    - Add diagnostic recommendations
    - _Requirements: 14.5, 14.7_
  
  - [x] 26.4 Write unit tests for P&L attribution
    - Test Greeks P&L decomposition accuracy
    - Test alpha/beta separation
    - Test regime-conditional statistics
    - _Requirements: 14.1, 14.2, 14.3_

- [x] 27. Checkpoint - Execution and monitoring operational
  - Verify execution interface generates correct orders
  - Verify performance monitoring tracks P&L accurately
  - Test attribution logic with historical data
  - Ensure all tests pass, ask the user if questions arise.


### Phase 7: System Integration and End-to-End Testing

- [x] 28. Wire all components together
  - [x] 28.1 Create unified volatility engine orchestrator
    - Implement src/volatility/unified_engine.py as main orchestrator
    - Wire VolatilityStateEngine, StrategyGenerator, GreeksAggregator, RiskAuthority
    - Integrate DispersionModule, GammaScalper, CapitalAllocator, MonteCarloEngine
    - Add RegimeDetector integration
    - _Requirements: 1.1, 1.2_
  
  - [x] 28.2 Implement data flow pipeline
    - Add market data ingestion → state construction → strategy generation flow
    - Implement risk validation → capital allocation → execution flow
    - Add Greeks monitoring → performance attribution feedback loop
    - _Requirements: 1.2, 1.3_
  
  - [x] 28.3 Add component communication interfaces
    - Define clear interfaces between all components
    - Implement event-driven updates for state changes
    - Add error handling and recovery at component boundaries
    - _Requirements: 11.6_
  
  - [x] 28.4 Write integration tests for complete flow
    - Test market data → strategy → execution complete flow
    - Test regime change propagation through all components
    - Test emergency action triggering and execution
    - _Requirements: 13.5_

- [x] 29. Implement regime transition testing
  - [x] 29.1 Write property tests for regime transitions
    - **Property 17: Strategy behavior stable across regime transitions**
    - *For any* rapid regime change, all strategy components should remain operational and not crash
    - **Validates: Requirements 13.3**
  
  - [x] 29.2 Write integration tests for regime transitions
    - Test low-vol → high-vol transition
    - Test high-vol → crisis transition
    - Test crisis → recovery transition
    - _Requirements: 13.3_

- [x] 30. Implement comprehensive system testing
  - [x] 30.1 Write end-to-end integration tests
    - Test complete trading day simulation
    - Test multi-strategy portfolio management
    - Test concurrent dispersion and gamma scalping
    - _Requirements: 13.5_
  
  - [x] 30.2 Write stress test validation
    - Verify 2008 crisis scenario handling
    - Verify 2020 COVID crash scenario handling
    - Verify combined crisis scenario survival
    - _Requirements: 13.2_
  
  - [x] 30.3 Write state persistence tests
    - Test state save and restore across system restart
    - Test recovery from corrupted state
    - Test state validation on load
    - _Requirements: 13.6_

- [x] 31. Performance optimization and validation
  - [x] 31.1 Optimize critical paths
    - Profile Greeks computation performance (target <50ms)
    - Profile state update propagation (target <100ms)
    - Optimize Monte Carlo simulation (parallel execution)
    - _Requirements: 3.1, 1.2_
  
  - [x] 31.2 Add performance benchmarks
    - Create benchmark suite for all critical operations
    - Set performance baselines
    - Add regression testing for performance
    - _Requirements: 3.1, 1.2_
  
  - [x] 31.3 Write performance tests
    - Test Greeks computation latency
    - Test state update latency
    - Test strategy generation latency
    - _Requirements: 3.1, 1.2_

- [x] 32. Documentation and deployment preparation
  - [x] 32.1 Create system documentation
    - Document unified architecture and component interactions
    - Create API documentation for all public interfaces
    - Write operator guide for system configuration
    - Document emergency procedures
    - _Requirements: 11.7, 15.7_
  
  - [x] 32.2 Create migration guide
    - Document changes from old architecture
    - Provide code migration examples
    - List deprecated components and replacements
    - _Requirements: 11.7_
  
  - [x] 32.3 Create deployment checklist
    - List all configuration parameters to set
    - Document data dependencies and initialization
    - Create system health check procedures
    - _Requirements: 15.1, 15.7_

- [x] 33. Final checkpoint - System complete
  - Run full test suite (unit, property, integration, stress)
  - Verify all requirements covered by tests
  - Validate system performance meets targets
  - Review documentation completeness
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional testing tasks that can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation at major milestones
- Property tests validate universal correctness properties across random inputs
- Unit tests validate specific examples and edge cases
- Integration tests validate end-to-end system behavior
- The implementation follows a bottom-up approach: cleanup → infrastructure → components → integration
- All duplicate components are archived (not deleted) to preserve history
- Clear module boundaries established before building new functionality
- Risk Authority operates independently with absolute veto power
- All components adapt behavior based on volatility regime
- Greeks are first-class citizens tracked in real-time
- Monte Carlo simulations use realistic fat-tailed distributions
- System designed for institutional-grade reliability and performance

