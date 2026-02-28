# Implementation Plan: Options Trading System

## Overview

This implementation plan breaks down the options trading system into discrete, incremental tasks. Each task builds on previous work, with testing integrated throughout. The plan follows the architecture defined in the design document and integrates seamlessly with the existing Northstar v3 infrastructure.

## Implementation Approach

- **Language**: Python 3.10+
- **Integration**: Extends existing Northstar v3 system
- **Testing**: Property-based tests (hypothesis) + unit tests (pytest)
- **Data**: Parquet files for immutable ledger, UnifiedState for live data
- **API**: Upstox API v2/v3 for options data

## Tasks

- [x] 1. Set up options trading infrastructure
  - Create directory structure: `src/options/`, `tests/options/`, `config/options/`
  - Create base configuration file: `config/options_trading.yaml`
  - Set up environment variables for Upstox credentials
  - Create options-specific logging configuration
  - _Requirements: US-11.1, US-11.2, US-11.3_

- [x] 1.1 Write unit tests for configuration loading
  - Test config file parsing and validation
  - Test environment variable loading
  - Test missing/invalid config handling
  - _Requirements: US-11.5_

- [x] 2. Implement Upstox API adapter
  - [x] 2.1 Create UpstoxAdapter class with authentication
    - Implement OAuth token management
    - Implement automatic token refresh
    - Add rate limiting (1 request/second)
    - _Requirements: US-1.1, US-1.5, US-1.6_
  
  - [ ]* 2.2 Write property test for rate limiting
    - **Property 4: Rate Limiting Enforcement**
    - **Validates: Requirements US-1.6**
  
  - [x] 2.3 Implement fetch_option_chain() using Put/Call Option Chain API
    - Call `/v2/option/chain` endpoint
    - Parse nested JSON response (call_options/put_options)
    - Extract market data and Greeks
    - Handle API errors with exponential backoff
    - _Requirements: US-1.1, US-1.2_
  
  - [ ]* 2.4 Write property test for API data completeness
    - **Property 1: API Data Completeness**
    - **Validates: Requirements US-1.2**
  
  - [x] 2.5 Implement fetch_option_greeks() using Option Greeks API
    - Call `/v3/market-quote/option-greek` endpoint
    - Support up to 50 instrument keys per request
    - Parse response and return DataFrame
    - _Requirements: US-1.1, US-1.2_
  
  - [x] 2.6 Implement data normalization to parquet format
    - Flatten nested API response
    - Map fields to pipeline schema
    - Validate data types and ranges
    - _Requirements: US-1.3_
  
  - [ ]* 2.7 Write property test for data normalization round-trip
    - **Property 2: Data Normalization Round-Trip**
    - **Validates: Requirements US-1.3**
  
  - [ ]* 2.8 Write property test for adapter interface compatibility
    - **Property 3: Adapter Interface Compatibility**
    - **Validates: Requirements US-1.4**

- [x] 3. Checkpoint - Verify Upstox adapter works
  - Test with real Upstox credentials (if available) or mock data
  - Verify option chain fetch and normalization
  - Ensure all tests pass
  - Ask user if questions arise

- [x] 4. Implement regime detection engine
  - [x] 4.1 Create RegimeDetector class
    - Implement IV percentile rank calculation (252-day history)
    - Implement IV position (min-max normalized) calculation
    - Implement IV trend calculation (5-day vs 20-day MA)
    - Implement skew calculation
    - Implement vol-of-vol check
    - _Requirements: US-2.1, US-2.2, US-2.5_
  
  - [ ]* 4.2 Write property test for regime classification domain
    - **Property 6: Regime Classification Domain**
    - **Validates: Requirements US-2.1**
  
  - [ ]* 4.3 Write property test for regime input sensitivity
    - **Property 7: Regime Input Sensitivity**
    - **Validates: Requirements US-2.2**
  
  - [x] 4.4 Implement regime persistence tracking
    - Store regime history in UnifiedState
    - Track days in current regime
    - Implement 2-day persistence requirement
    - _Requirements: US-2.3_
  
  - [ ]* 4.5 Write property test for regime persistence requirement
    - **Property 8: Regime Persistence Requirement**
    - **Validates: Requirements US-2.3, US-4.1**
  
  - [x] 4.6 Implement equity crisis regime integration
    - Read underlying equity regime from Northstar v3 state
    - Block short-vol if equity regime = CRISIS
    - _Requirements: US-2.1, US-2.2_
  
  - [ ]* 4.7 Write property test for vol-of-vol short-vol block
    - **Property 9: Vol-of-Vol Short-Vol Block**
    - **Validates: Requirements US-2.5, US-4.7**
  
  - [ ]* 4.8 Write property test for equity crisis regime block
    - **Property 46: Equity Crisis Regime Block**
    - **Validates: Requirements US-2.1, US-2.2**

- [x] 5. Implement strategy generation engine
  - [x] 5.1 Create StrategyGenerator class and data models
    - Define OptionStrategy, OptionLeg, Greeks dataclasses
    - Implement strategy type enum
    - _Requirements: US-3.1, US-3.2, US-3.3_
  
  - [x] 5.2 Implement Iron Condor strategy generation
    - Select strikes based on delta (16-20 for short, 5-10 for long)
    - Calculate max loss, max profit, net credit
    - Validate lot sizes (50 for NIFTY, 15 for BANKNIFTY)
    - Check premium adequacy (credit ≥ 0.25 × max loss)
    - _Requirements: US-3.1, US-3.5, US-3.6_
  
  - [x] 5.3 Implement Calendar Spread strategy generation
    - Select ATM strikes
    - Choose near-term (7-14 days) and far-term (30-45 days) expiries
    - Calculate max loss (net debit)
    - _Requirements: US-3.2, US-3.5_
  
  - [x] 5.4 Implement Long Straddle strategy generation
    - Select ATM strike
    - Choose expiry (30-60 days)
    - Calculate max loss (total premium)
    - _Requirements: US-3.3, US-3.5_
  
  - [ ]* 5.5 Write property test for regime-strategy mapping
    - **Property 10: Regime-Strategy Mapping**
    - **Validates: Requirements US-3.1, US-3.2, US-3.3**
  
  - [ ]* 5.6 Write property test for strategy data completeness
    - **Property 11: Strategy Data Completeness**
    - **Validates: Requirements US-3.4**
  
  - [ ]* 5.7 Write property test for lot size constraint
    - **Property 12: Lot Size Constraint**
    - **Validates: Requirements US-3.5**
  
  - [ ]* 5.8 Write property test for premium adequacy
    - **Property 13: Premium Adequacy**
    - **Validates: Requirements US-3.6**

- [x] 6. Checkpoint - Verify strategy generation
  - Test strategy generation for each regime
  - Verify lot size validation
  - Ensure all tests pass
  - Ask user if questions arise

- [x] 7. Implement trade eligibility validator
  - [x] 7.1 Create TradeEligibilityValidator class
    - Implement validation result dataclass
    - Create validation rule framework
    - _Requirements: US-4.1 through US-4.8_
  
  - [x] 7.2 Implement IV rank threshold checks
    - LOW_VOL_SELL: IV rank > 70%
    - HIGH_VOL_SELL: IV rank > 80%
    - RISING_VOL_BUY: IV rank < 30%
    - _Requirements: US-4.2_
  
  - [ ]* 7.3 Write property test for IV rank threshold enforcement
    - **Property 14: IV Rank Threshold Enforcement**
    - **Validates: Requirements US-4.2**
  
  - [x] 7.4 Implement liquidity checks
    - Bid-ask spread ≤ 8% of mid premium
    - Bid quantity ≥ 2 × required lot size
    - _Requirements: US-4.3, US-4.4_
  
  - [ ]* 7.5 Write property test for liquidity spread check
    - **Property 15: Liquidity Spread Check**
    - **Validates: Requirements US-4.3**
  
  - [ ]* 7.6 Write property test for liquidity depth check
    - **Property 16: Liquidity Depth Check**
    - **Validates: Requirements US-4.4**
  
  - [x] 7.7 Implement expiry hygiene check
    - Reject trades with < 5 days to expiry
    - _Requirements: US-4.5_
  
  - [ ]* 7.8 Write property test for expiry hygiene
    - **Property 17: Expiry Hygiene**
    - **Validates: Requirements US-4.5**
  
  - [x] 7.9 Implement event calendar check
    - Load macro events from config
    - Block short-vol within 2 days of events
    - _Requirements: US-4.6, US-11.4_
  
  - [ ]* 7.10 Write property test for event calendar block
    - **Property 18: Event Calendar Block**
    - **Validates: Requirements US-4.6**
  
  - [x] 7.11 Implement late-cycle protection
    - Reduce position size by 50% if LOW_VOL_SELL > 10 days
    - _Requirements: US-4.8_
  
  - [ ]* 7.12 Write property test for late-cycle size reduction
    - **Property 19: Late-Cycle Size Reduction**
    - **Validates: Requirements US-4.8**

- [x] 8. Implement capital scaling engine
  - [x] 8.1 Create CapitalScalingEngine class
    - Define ScalingState dataclass
    - Implement base capital and risk parameters
    - _Requirements: US-5.1_
  
  - [x] 8.2 Implement profit scaling logic
    - +0.25% risk per 8% profit milestone
    - Track equity high water mark
    - _Requirements: US-5.2_
  
  - [ ]* 8.3 Write property test for profit scaling trigger
    - **Property 21: Profit Scaling Trigger**
    - **Validates: Requirements US-5.2**
  
  - [x] 8.4 Implement risk ceiling enforcement
    - Max 1.5% risk per trade (hard cap)
    - _Requirements: US-5.3_
  
  - [ ]* 8.5 Write property test for risk ceiling invariant
    - **Property 20: Risk Ceiling Invariant**
    - **Validates: Requirements US-5.3**
  
  - [x] 8.6 Implement drawdown de-scaling
    - -0.25% at 3% drawdown
    - -0.50% at 5% drawdown
    - _Requirements: US-5.4_
  
  - [ ]* 8.7 Write property test for drawdown de-scaling
    - **Property 22: Drawdown De-Scaling**
    - **Validates: Requirements US-5.4**
  
  - [x] 8.8 Implement recovery condition logic
    - Require equity at previous high + 2 profitable trades
    - _Requirements: US-5.5_
  
  - [ ]* 8.9 Write property test for recovery condition
    - **Property 23: Recovery Condition**
    - **Validates: Requirements US-5.5**
  
  - [x] 8.10 Implement time requirement check
    - No scaling before 8 consecutive weeks
    - _Requirements: US-5.6_
  
  - [ ]* 8.11 Write property test for scaling time requirement
    - **Property 24: Scaling Time Requirement**
    - **Validates: Requirements US-5.6**

- [x] 9. Checkpoint - Verify eligibility and scaling
  - Test trade eligibility validation with various scenarios
  - Test capital scaling with profit/drawdown scenarios
  - Ensure all tests pass
  - Ask user if questions arise

- [x] 10. Implement survival rules engine
  - [x] 10.1 Create SurvivalRulesEngine class
    - Define KillSwitchStatus dataclass
    - Implement kill switch state tracking in UnifiedState
    - _Requirements: US-6.1 through US-6.6_
  
  - [x] 10.2 Implement weekly loss kill switch
    - Track weekly P&L (Monday 00:00 to Sunday 23:59 IST)
    - Halt trading if loss ≥ 2% capital
    - Reset at Monday 9:15 AM IST
    - _Requirements: US-6.1_
  
  - [ ]* 10.3 Write property test for weekly loss kill switch
    - **Property 25: Weekly Loss Kill Switch**
    - **Validates: Requirements US-6.1**
  
  - [x] 10.4 Implement trauma rule
    - Block short-vol for 2 weeks if trade loses > 80% max loss
    - _Requirements: US-6.2_
  
  - [ ]* 10.5 Write property test for trauma rule activation
    - **Property 26: Trauma Rule Activation**
    - **Validates: Requirements US-6.2**
  
  - [x] 10.6 Implement portfolio risk cap
    - Sum max losses across open positions
    - Reject if total > 2% capital
    - _Requirements: US-6.3_
  
  - [ ]* 10.7 Write property test for portfolio risk cap
    - **Property 27: Portfolio Risk Cap**
    - **Validates: Requirements US-6.3**
  
  - [x] 10.8 Implement tax liquidity check
    - Calculate YTD tax liability
    - Halt if tax > cash buffer
    - _Requirements: US-6.4_
  
  - [ ]* 10.9 Write property test for tax liquidity check
    - **Property 28: Tax Liquidity Check**
    - **Validates: Requirements US-6.4**
  
  - [x] 10.10 Implement frequency limits
    - Max 2 trades per week
    - No trading Monday 9:15-10:00 AM IST
    - No trading on expiry days (Thursday)
    - _Requirements: US-6.5, US-6.6_
  
  - [ ]* 10.11 Write property test for weekly trade frequency limit
    - **Property 29: Weekly Trade Frequency Limit**
    - **Validates: Requirements US-6.5**
  
  - [ ]* 10.12 Write property test for time-based trade blocks
    - **Property 30: Time-Based Trade Blocks**
    - **Validates: Requirements US-6.6**

- [x] 11. Implement position management system
  - [x] 11.1 Create PositionManager class
    - Define Position, PositionLeg dataclasses
    - Implement position state tracking in UnifiedState
    - _Requirements: US-7.1_
  
  - [ ]* 11.2 Write property test for position data completeness
    - **Property 31: Position Data Completeness**
    - **Validates: Requirements US-7.1**
  
  - [x] 11.3 Implement open_position() method
    - Create position from strategy
    - Store in UnifiedState
    - Publish position_opened event
    - _Requirements: US-7.1_
  
  - [x] 11.4 Implement mark-to-market calculation
    - Fetch current option premiums
    - Calculate current value and unrealized P&L
    - Update position in UnifiedState
    - _Requirements: US-7.2_
  
  - [ ]* 11.5 Write property test for MTM responsiveness
    - **Property 32: MTM Responsiveness**
    - **Validates: Requirements US-7.2**
  
  - [x] 11.6 Implement exit condition checks
    - 55% profit target
    - 40% stop loss
    - 2 days before expiry
    - Regime flip
    - Greek violations
    - Exit rule precedence logic
    - _Requirements: US-7.3_
  
  - [ ]* 11.7 Write property test for exit condition triggers
    - **Property 33: Exit Condition Triggers**
    - **Validates: Requirements US-7.3**
  
  - [x] 11.8 Implement close_position() method
    - Calculate final P&L
    - Update position status to closed
    - Publish position_closed event
    - _Requirements: US-7.3_
  
  - [x] 11.9 Implement portfolio Greeks aggregation
    - Sum Greeks across all open positions
    - _Requirements: US-7.4_
  
  - [ ]* 11.10 Write property test for portfolio Greeks aggregation
    - **Property 34: Portfolio Greeks Aggregation**
    - **Validates: Requirements US-7.4**
  
  - [x] 11.11 Implement Greek safety band checks
    - Delta: [-0.2, +0.2]
    - Theta: > 0
    - Vega: [-0.3, +0.1]
    - Gamma escalation logic
    - _Requirements: US-7.5_
  
  - [ ]* 11.12 Write property test for Greek safety band violations
    - **Property 35: Greek Safety Band Violations**
    - **Validates: Requirements US-7.5**

- [x] 12. Checkpoint - Verify position management
  - Test position lifecycle (open → MTM → exit)
  - Test Greek aggregation and safety bands
  - Ensure all tests pass
  - Ask user if questions arise

- [x] 13. Implement tax-aware P&L tracker
  - [x] 13.1 Create TaxAwarePnLTracker class
    - Define TradeCosts dataclass
    - Implement cost calculation methods
    - _Requirements: US-8.1, US-8.2_
  
  - [x] 13.2 Implement gross P&L calculation
    - Formula: exit_value - entry_credit_debit
    - _Requirements: US-8.1_
  
  - [ ]* 13.3 Write property test for gross P&L formula
    - **Property 36: Gross P&L Formula**
    - **Validates: Requirements US-8.1**
  
  - [x] 13.4 Implement cost calculation
    - Brokerage: ₹20 per leg
    - Exchange charges: 0.05% of turnover
    - SEBI charges: ₹10 per crore
    - Stamp duty: 0.003% on buy side
    - GST: 18% on (brokerage + exchange charges)
    - _Requirements: US-8.2_
  
  - [ ]* 13.5 Write property test for cost completeness
    - **Property 37: Cost Completeness**
    - **Validates: Requirements US-8.2**
  
  - [x] 13.6 Implement tax calculation
    - 30% on gross profit (if positive)
    - 0% on losses
    - Applied on close date only (not MTM)
    - _Requirements: US-8.3_
  
  - [ ]* 13.7 Write property test for tax calculation
    - **Property 38: Tax Calculation**
    - **Validates: Requirements US-8.3**
  
  - [x] 13.8 Implement net P&L calculation
    - Formula: gross_pnl - costs - tax
    - _Requirements: US-8.4_
  
  - [ ]* 13.9 Write property test for net P&L formula
    - **Property 39: Net P&L Formula**
    - **Validates: Requirements US-8.4**
  
  - [x] 13.10 Implement minimum profitability filter
    - Reject if expected net P&L < 1.5 × costs
    - _Requirements: US-8.5_
  
  - [ ]* 13.11 Write property test for minimum profitability filter
    - **Property 40: Minimum Profitability Filter**
    - **Validates: Requirements US-8.5**
  
  - [x] 13.12 Implement YTD tax liability tracking
    - Sum taxes on all profitable closed trades
    - _Requirements: US-8.6_
  
  - [ ]* 13.13 Write property test for YTD tax liability aggregation
    - **Property 41: YTD Tax Liability Aggregation**
    - **Validates: Requirements US-8.6**

- [x] 14. Implement immutable trade ledger
  - [x] 14.1 Create trade ledger schema (parquet)
    - Define schema with all required fields
    - Implement append-only write logic
    - Store in `data/options/trade_ledger.parquet`
    - _Requirements: US-7.6_
  
  - [x] 14.2 Implement ledger write operations
    - Write trade on position open
    - Write trade on position close
    - Never modify existing records
    - _Requirements: US-7.6_
  
  - [ ]* 14.3 Write property test for trade ledger immutability
    - **Property 5: Trade Ledger Immutability**
    - **Validates: Requirements US-7.6**

- [x] 15. Implement system hygiene rules
  - [x] 15.1 Implement strategy concentration limit
    - Track last 2 trades
    - Reject 3rd consecutive trade of same type
    - _Requirements: US-10.1_
  
  - [ ]* 15.2 Write property test for strategy concentration limit
    - **Property 44: Strategy Concentration Limit**
    - **Validates: Requirements US-10.1**
  
  - [x] 15.3 Implement success cooling period
    - Track last 2 trades
    - Skip signal after 2 consecutive wins (unless IV extreme)
    - _Requirements: US-10.2_
  
  - [ ]* 15.4 Write property test for success cooling period
    - **Property 45: Success Cooling Period**
    - **Validates: Requirements US-10.2**

- [x] 16. Checkpoint - Verify P&L and ledger
  - Test P&L calculation with realistic scenarios
  - Test trade ledger append-only behavior
  - Ensure all tests pass
  - Ask user if questions arise

- [x] 17. Integrate with Northstar v3 risk system
  - [x] 17.1 Create OptionsRiskValidator for RiskCoordinator
    - Implement RiskValidator interface
    - Add options-specific risk checks
    - Integrate with existing risk hierarchy
    - _Requirements: US-6.1 through US-6.6_
  
  - [x] 17.2 Register options risk validator with RiskCoordinator
    - Add to risk validator chain
    - Ensure options risks are checked before trade approval
    - _Requirements: US-6.1 through US-6.6_
  
  - [x] 17.3 Publish options events to UnifiedState event bus
    - regime_change events
    - position_update events
    - trade_signal events
    - kill_switch events
    - _Requirements: US-9.1 through US-9.7_

- [x] 18. Implement dashboard integration
  - [x] 18.1 Create OptionsObserver class
    - Subscribe to options events from event bus
    - Update dashboard state on events
    - _Requirements: US-9.1 through US-9.7_
  
  - [x] 18.2 Create OptionsPanel Streamlit component
    - Display current regime, IV rank, vol-of-vol status
    - Display active positions table with P&L and Greeks
    - Display portfolio Greeks chart (time series)
    - Display trade history with metrics
    - Display risk metrics (weekly risk used, capital scaling)
    - Display kill switch status
    - Display next trade eligibility with reasons
    - _Requirements: US-9.1 through US-9.7_
  
  - [ ]* 18.3 Write unit tests for dashboard data structures
    - Test that dashboard state contains all required fields
    - Test trade history metrics calculation
    - _Requirements: US-9.2, US-9.3, US-9.5, US-9.6_
  
  - [ ]* 18.4 Write property test for trade history metrics
    - **Property 42: Trade History Metrics**
    - **Validates: Requirements US-9.5**
  
  - [ ]* 18.5 Write property test for trade rejection reasons
    - **Property 43: Trade Rejection Reasons**
    - **Validates: Requirements US-9.7**
  
  - [x] 18.6 Integrate OptionsPanel into main dashboard
    - Add options panel to dashboard layout
    - Configure refresh interval (5 seconds)
    - _Requirements: US-9.1_

- [x] 19. Implement backtesting support
  - [x] 19.1 Create historical data loader
    - Support loading historical option chain data
    - Validate temporal consistency
    - _Requirements: US-12.1_
  
  - [x] 19.2 Create backtest simulation engine
    - Simulate 8-week trading periods
    - Apply all eligibility rules
    - Apply all survival rules
    - Include realistic slippage (1-2%)
    - _Requirements: US-12.2_
  
  - [x] 19.3 Implement backtest reporting
    - Calculate win rate, net P&L, max drawdown
    - Track Greek violations
    - Track kill switch activations
    - _Requirements: US-12.4_
  
  - [ ]* 19.4 Write property test for backtest cost inclusion
    - **Property 47: Backtest Cost Inclusion**
    - **Validates: Requirements US-12.3**
  
  - [x] 19.5 Create stress test scenarios
    - Vol expansion scenario
    - Calendar spread failure scenario
    - Consecutive losses scenario
    - _Requirements: US-12.5_

- [x] 20. Final checkpoint - End-to-end integration test
  - Run complete signal generation pipeline
  - Test with mock Upstox data
  - Verify dashboard displays correctly
  - Verify all kill switches work
  - Verify trade ledger is written correctly
  - Ensure all tests pass
  - Ask user if questions arise

- [x] 21. Documentation and deployment preparation
  - [x] 21.1 Create user guide for options trading system
    - How to configure Upstox credentials
    - How to interpret dashboard signals
    - How to manually execute trades
    - How to monitor positions
  
  - [x] 21.2 Create operator runbook
    - How to handle kill switch activations
    - How to review rejected trades
    - How to audit trade ledger
    - How to update event calendar
  
  - [x] 21.3 Create deployment checklist
    - Verify Upstox API access
    - Verify configuration file
    - Verify environment variables
    - Run all tests
    - Verify dashboard integration

- [x] 22. Dry run validation system
  - [x] 22.1 Create dry run script with real API data
    - Fetch live option chains from Upstox
    - Run complete signal generation pipeline
    - Log all decisions without executing trades
    - Track signal frequency and quality
  
  - [x] 22.2 Create dry run monitoring and reporting
    - Daily summary reports
    - Final validation report
    - Signal frequency analysis (~2/week target)
    - Regime detection accuracy tracking
    - Kill switch behavior validation
  
  - [x] 22.3 Create dry run guide
    - Setup instructions with API credentials
    - Single cycle vs continuous monitoring
    - Output file descriptions
    - Validation criteria (PASS/FAIL)
    - Troubleshooting common issues
    - Configuration tuning guidelines

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties (min 100 iterations each)
- Unit tests validate specific examples and edge cases
- All property tests must include tag: `# Feature: options-trading-system, Property {N}: {property_text}`
- Integration with existing Northstar v3 components (UnifiedState, RiskCoordinator, Dashboard) is critical
- Manual execution model means no automated order placement - system generates signals only
