# Requirements Document: Institutional Validation Layers

## Introduction

This specification defines the implementation of a four-layer institutional-grade validation framework for Northstar V3. The system transforms Northstar from a research-grade portfolio system into an investment-grade platform with undeniable proof of value, survival capability, anticipatory intelligence, and live reality validation. This framework is designed to meet the standards expected by institutional investors like Accel Partners.

## Glossary

- **Northstar_System**: The complete Northstar V3 investment organism including Market Brain, Portfolio Governor, Risk Coordinator, and Intelligence Stack
- **Performance_Summary**: Monthly performance metrics table tracking returns, costs, risk, and benchmark comparison
- **Shadow_Fund**: Virtual portfolio that trades in real market time with real prices but virtual money
- **Kill_Switch**: Automatic risk brake that reduces exposure when danger thresholds are exceeded
- **Regime_Memory**: Historical database of market regimes with macro embeddings and strategy performance
- **Beta_Drift**: Changes in stock-macro factor relationships detected through rolling regression analysis
- **Strategy_Tailwind**: Forward-looking edge metric combining Sharpe ratio with beta drift signals
- **Anticipatory_Intelligence**: System capability to position before price moves by detecting causal conditions
- **Point_In_Time_Validation**: Backtest methodology ensuring no lookahead bias using only past data
- **NIFTY**: National Stock Exchange of India benchmark index used for performance comparison
- **Active_Share**: Metric measuring portfolio differentiation from benchmark (0-100%)
- **Transaction_Cost_Model**: Realistic cost estimation including brokerage, slippage, and market impact
- **Drawdown**: Maximum peak-to-trough decline in portfolio value
- **Risk_Budget**: Sector-level risk allocation limits enforced by the system
- **Stress_Test**: Historical crisis scenario replay to validate downside protection
- **Regime_Fingerprint**: 16-dimensional macro embedding vector characterizing market conditions
- **Causal_Fabric**: Weekly database of stock-macro relationships and their changes
- **Forward_Validation**: Test proving allocation shifts occurred before price movements
- **Data_Provenance**: Complete audit trail of data sources, versions, and transformations used in decisions
- **Run_Manifest**: Cryptographically signed record of all data and code used in a specific system run
- **Execution_Model**: Simulation of real trading friction including partial fills, slippage, and market impact
- **Signal_Decay**: Degradation of strategy signal predictive power over time indicating potential overfitting
- **Strategy_Redundancy**: High correlation between strategies indicating hidden concentration risk
- **Out_Of_Sample_Test**: Validation on unseen data periods to verify strategy edge is not overfit
- **Governance_System**: Human oversight layer allowing documented overrides and emergency controls
- **Human_Override**: Documented intervention by authorized personnel to pause, limit, or modify system behavior
- **NO_EDGE_State**: System state where insufficient confidence exists to deploy capital, triggering defensive positioning
- **Belief_Confidence**: Quantitative measure (0.0 to 1.0) of system confidence in its regime detection, tailwinds, and allocations
- **Causality_Index**: Human-readable summary of top drivers causing allocation changes each month
- **Confidence_Score**: Numerical measure of system conviction based on regime similarity, beta drift consistency, signal stability, and data freshness

## Requirements

### Requirement 1: Point-in-Time Performance Tracking

**User Story:** As an institutional investor, I want undeniable proof that Northstar generates alpha after costs with no lookahead bias, so that I can trust the backtest results represent real trading performance.

#### Acceptance Criteria

1. WHEN the system runs monthly performance calculation, THE Performance_Tracker SHALL compute returns using only data available at decision time
2. WHEN computing monthly returns, THE Performance_Tracker SHALL use weights from the previous month's signal and evaluate returns in the current month
3. WHEN generating performance summary, THE Performance_Tracker SHALL include date, northstar_return, nifty_return, exposure, active_share, turnover, drawdown, transaction_costs, net_return, and volatility columns
4. WHEN calculating transaction costs, THE Transaction_Cost_Model SHALL apply 0.05% base cost plus slippage based on turnover and liquidity
5. WHEN computing net returns, THE Performance_Tracker SHALL subtract transaction costs from gross returns
6. WHEN calculating active share, THE Performance_Tracker SHALL measure portfolio differentiation from NIFTY using weight differences
7. WHEN measuring turnover, THE Performance_Tracker SHALL compute half the sum of absolute weight changes between periods
8. WHEN tracking drawdown, THE Performance_Tracker SHALL compute running maximum decline from peak portfolio value
9. WHEN calculating volatility, THE Performance_Tracker SHALL use 60-day rolling standard deviation of returns
10. THE Performance_Tracker SHALL persist results to data/processed/performance_summary.parquet with proper schema

### Requirement 2: Benchmark Comparison and Visualization

**User Story:** As a fund manager, I want clear visual proof that Northstar outperforms NIFTY, so that I can demonstrate value to stakeholders.

#### Acceptance Criteria

1. WHEN generating performance charts, THE Visualization_Engine SHALL plot Northstar cumulative return against NIFTY cumulative return
2. WHEN computing cumulative returns, THE Visualization_Engine SHALL compound monthly returns starting from base value 100
3. WHEN creating comparison charts, THE Visualization_Engine SHALL use blue line for Northstar and gray line for NIFTY
4. WHEN calculating Sharpe ratio, THE Performance_Analyzer SHALL compute mean excess return divided by standard deviation
5. WHEN measuring win rate, THE Performance_Analyzer SHALL compute percentage of months with positive returns
6. WHEN computing rolling alpha, THE Performance_Analyzer SHALL calculate 3-month rolling outperformance versus NIFTY
7. THE Visualization_Engine SHALL save charts to docs/figures/northstar_vs_nifty_12m.png
8. THE Performance_Analyzer SHALL target Sharpe ratio above 1.0 and win rate between 55-70%

### Requirement 3: Automatic Portfolio Kill Switches

**User Story:** As a risk manager, I want the system to automatically reduce exposure when markets become dangerous, so that catastrophic losses are prevented.

#### Acceptance Criteria

1. WHEN portfolio drawdown exceeds 20%, THE Kill_Switch_System SHALL reduce exposure to 50% of current level
2. WHEN daily loss exceeds 5%, THE Kill_Switch_System SHALL reduce exposure to 25% of current level
3. WHEN 30-day realized volatility exceeds 30%, THE Kill_Switch_System SHALL cap exposure at 60%
4. WHEN kill switch activates, THE Kill_Switch_System SHALL log activation to data/risk/risk_state.parquet
5. WHEN computing realized volatility, THE Kill_Switch_System SHALL use 30-day rolling window annualized
6. THE Kill_Switch_System SHALL track portfolio_value, drawdown, daily_return, realized_vol, risk_level, emergency_active, and exposure_cap daily
7. THE Kill_Switch_System SHALL generate emergency activation visualization showing red dots on exposure timeline

### Requirement 4: Risk Budget Enforcement

**User Story:** As a portfolio manager, I want sector risk limits automatically enforced, so that I don't accidentally concentrate risk in one sector.

#### Acceptance Criteria

1. WHEN sector risk exceeds defined limits, THE Risk_Budget_System SHALL scale down positions proportionally
2. WHEN enforcing risk budgets, THE Risk_Budget_System SHALL track sector, max_risk, current_risk, and utilization
3. WHEN a sector exceeds its risk budget, THE Risk_Budget_System SHALL reduce all positions in that sector proportionally
4. THE Risk_Budget_System SHALL persist risk budget state to data/risk/risk_budget.parquet
5. THE Risk_Budget_System SHALL define default sector limits: Banks 10%, IT 8%, Metals 6%, Pharma 7%

### Requirement 5: Historical Crisis Stress Testing

**User Story:** As an institutional investor, I want proof that Northstar survives historical crises better than the benchmark, so that I can trust downside protection.

#### Acceptance Criteria

1. WHEN running stress tests, THE Stress_Test_Engine SHALL replay COVID crash (2020-02-20 to 2020-03-23)
2. WHEN running stress tests, THE Stress_Test_Engine SHALL replay 2008 crisis (2008-09-01 to 2009-03-01) if data available
3. WHEN running stress tests, THE Stress_Test_Engine SHALL replay 2022 bear market (2022-01-01 to 2022-06-30)
4. WHEN computing crisis performance, THE Stress_Test_Engine SHALL track scenario, start_date, end_date, northstar_return, nifty_return, and max_drawdown
5. WHEN a crisis is replayed, THE Stress_Test_Engine SHALL verify Northstar drawdown is less than NIFTY drawdown
6. THE Stress_Test_Engine SHALL persist results to data/risk/stress_tests.parquet

### Requirement 6: Shadow-Live Trading Simulation

**User Story:** As a fund manager, I want to run Northstar with real prices and real costs before deploying real money, so that I can validate it works in live markets.

#### Acceptance Criteria

1. WHEN shadow fund operates, THE Shadow_Fund_Engine SHALL log daily positions to data/shadow_fund/trades.parquet
2. WHEN recording positions, THE Shadow_Fund_Engine SHALL track date, ticker, action, weight_before, weight_after, price, and slippage
3. WHEN computing shadow performance, THE Shadow_Fund_Engine SHALL track daily P&L with same schema as performance_summary
4. WHEN making decisions, THE Shadow_Fund_Engine SHALL log regime, tailwind_shift, exposure_change, risk_reason, strategies_boosted, strategies_cut, and emergency_triggered
5. THE Shadow_Fund_Engine SHALL operate in real market time with real prices but virtual money
6. THE Shadow_Fund_Engine SHALL apply realistic transaction costs and slippage to all trades

### Requirement 7: Regime Memory and Fingerprinting

**User Story:** As a quant researcher, I want the system to remember historical market regimes and detect similarity to current conditions, so that strategy allocation can anticipate regime-appropriate performance.

#### Acceptance Criteria

1. WHEN building regime memory, THE Regime_Memory_System SHALL create regime_id, start_date, end_date, regime_name, macro_embedding_16d, avg_vol, avg_liquidity, avg_drawdown, best_strategy, worst_strategy, and next_regime columns
2. WHEN computing regime similarity, THE Regime_Memory_System SHALL use cosine similarity between current macro vector and historical regime embeddings
3. WHEN similarity exceeds 0.7, THE Regime_Memory_System SHALL treat regimes as same family
4. WHEN detecting regime match, THE Regime_Memory_System SHALL identify historically best and worst performing strategies
5. THE Regime_Memory_System SHALL persist regime memory to data/intelligence/regime_memory.parquet
6. THE Regime_Memory_System SHALL compute 16-dimensional macro embeddings from current market conditions

### Requirement 8: Beta Drift Causal Fabric

**User Story:** As a systematic trader, I want to detect when stock-macro relationships are changing, so that I can position before price moves rather than reacting to price.

#### Acceptance Criteria

1. WHEN computing beta drift, THE Beta_Drift_System SHALL calculate 52-week rolling beta between each stock and macro factors
2. WHEN detecting drift, THE Beta_Drift_System SHALL flag relationships where beta change exceeds 1.5 standard deviations
3. WHEN storing weekly fabric, THE Beta_Drift_System SHALL track date, stock, macro_var, rolling_beta, beta_change, significance, direction, and forward_4w_return
4. WHEN organizing fabric files, THE Beta_Drift_System SHALL create weekly files at data/intelligence/weekly_causal_fabric/{year}/week_{n}.parquet
5. THE Beta_Drift_System SHALL compute beta as covariance(stock_return, macro_factor) / variance(macro_factor)
6. THE Beta_Drift_System SHALL track beta drift as current_beta minus previous_beta

### Requirement 9: Strategy Tailwind Computation

**User Story:** As a capital allocator, I want forward-looking edge metrics that combine historical performance with beta drift signals, so that capital moves before returns appear.

#### Acceptance Criteria

1. WHEN computing tailwinds, THE Tailwind_Engine SHALL track date, strategy, tailwind_score, risk_adjusted, regime, and key_driver
2. WHEN calculating tailwind score, THE Tailwind_Engine SHALL sum weighted beta drifts across macro factors the strategy is exposed to
3. WHEN adjusting for risk, THE Tailwind_Engine SHALL normalize tailwind by strategy volatility
4. WHEN allocating capital, THE Capital_Allocator SHALL use 60% Sharpe ratio plus 40% tailwind score for final skill metric
5. THE Tailwind_Engine SHALL persist tailwinds to data/intelligence/strategy_tailwinds.parquet
6. THE Tailwind_Engine SHALL identify key macro drivers causing tailwind changes

### Requirement 10: Forward Validation of Anticipation

**User Story:** As an institutional investor, I want proof that Northstar shifts allocation before price moves, so that I can verify true anticipatory intelligence rather than curve-fitting.

#### Acceptance Criteria

1. WHEN testing anticipation, THE Forward_Validator SHALL track date, regime, tailwind_shift, allocation_shift, next_4w_return, nifty_return, and northstar_advantage
2. WHEN tailwind turns negative, THE Forward_Validator SHALL verify Northstar reduced exposure before drawdown
3. WHEN allocation shifts occur, THE Forward_Validator SHALL measure subsequent 4-week outperformance
4. WHEN validating anticipation, THE Forward_Validator SHALL require allocation change preceded return change by at least 1 week
5. THE Forward_Validator SHALL persist anticipation tests to data/intelligence/anticipation_test.parquet
6. THE Forward_Validator SHALL target 3-5 successful anticipation events per year as proof of edge

### Requirement 11: Daily Shadow Portfolio Logging

**User Story:** As a compliance officer, I want complete daily logs of shadow portfolio positions and decisions, so that I can audit the system's behavior and verify transparency.

#### Acceptance Criteria

1. WHEN shadow fund operates daily, THE Shadow_Logger SHALL create daily_positions_YYYYMMDD.parquet files
2. WHEN logging positions, THE Shadow_Logger SHALL track date, ticker, weight, role, strategy_source, exposure, and risk_cap
3. WHEN logging P&L, THE Shadow_Logger SHALL create daily_pnl_YYYYMMDD.parquet with returns, tracking error, drawdown, turnover, and costs
4. WHEN logging decisions, THE Shadow_Logger SHALL create daily_decisions_YYYYMMDD.json with regime, tailwind_shift, exposure_change, risk_reason, strategies_boosted, strategies_cut, and emergency_triggered
5. THE Shadow_Logger SHALL organize files in data/live_shadow/{year}/ directory structure
6. THE Shadow_Logger SHALL ensure all logs are timestamped and immutable for audit purposes

### Requirement 12: Behavioral Stability Testing

**User Story:** As a risk manager, I want to verify the system is robust to input variations, so that I know it's not a fragile science experiment.

#### Acceptance Criteria

1. WHEN testing sensitivity, THE Stability_Tester SHALL run Northstar with different macro sources and verify correlation above 0.85
2. WHEN testing sensitivity, THE Stability_Tester SHALL vary rolling windows and verify results remain similar
3. WHEN testing sensitivity, THE Stability_Tester SHALL change transaction costs and verify system remains profitable
4. WHEN testing turnover control, THE Stability_Tester SHALL verify monthly turnover stays between 5-15%
5. WHEN testing regime consistency, THE Stability_Tester SHALL verify different behavior in late-expansion (70-90% exposure, momentum) versus recession (30-50% exposure, low-vol) versus liquidity-crisis (20-40% exposure, cash/value)
6. THE Stability_Tester SHALL generate stability report showing correlation between base and variant runs

### Requirement 13: Monthly Public Reporting

**User Story:** As a fund manager, I want to publish transparent monthly performance reports, so that stakeholders can verify results are real and timestamped.

#### Acceptance Criteria

1. WHEN month ends, THE Report_Generator SHALL create northstar_monthly_YYYYMM.pdf in data/public_reports/
2. WHEN generating report, THE Report_Generator SHALL include Northstar vs NIFTY cumulative return chart
3. WHEN generating report, THE Report_Generator SHALL include drawdown comparison chart
4. WHEN generating report, THE Report_Generator SHALL include exposure changes over the month
5. WHEN generating report, THE Report_Generator SHALL include regime calls and key wins/losses
6. WHEN generating report, THE Report_Generator SHALL include Sharpe ratio, win rate, and rolling alpha metrics
7. THE Report_Generator SHALL ensure reports are timestamped and cryptographically signed for authenticity

### Requirement 14: Integration with Existing V3 Architecture

**User Story:** As a system architect, I want the validation layers to integrate seamlessly with existing Northstar V3 components, so that the living system benefits are preserved.

#### Acceptance Criteria

1. WHEN validation layers operate, THE Integration_Layer SHALL use existing UnifiedState for state management
2. WHEN validation layers operate, THE Integration_Layer SHALL emit events through existing EventBus for observability
3. WHEN validation layers operate, THE Integration_Layer SHALL respect Risk_Coordinator authority for all risk decisions
4. WHEN validation layers operate, THE Integration_Layer SHALL use existing Market_Clock for time-driven behavior
5. WHEN validation layers operate, THE Integration_Layer SHALL integrate with existing Market_Brain for regime detection
6. WHEN validation layers operate, THE Integration_Layer SHALL integrate with existing Capital_Allocator for strategy allocation
7. WHEN validation layers operate, THE Integration_Layer SHALL integrate with existing Portfolio_Governor for position construction
8. THE Integration_Layer SHALL ensure zero breaking changes to existing V3 functionality

### Requirement 15: Performance Summary Schema Validation

**User Story:** As a data engineer, I want strict schema validation for all performance data, so that downstream analysis tools can rely on data quality.

#### Acceptance Criteria

1. WHEN persisting performance data, THE Schema_Validator SHALL enforce date as datetime type
2. WHEN persisting performance data, THE Schema_Validator SHALL enforce all return columns as float type
3. WHEN persisting performance data, THE Schema_Validator SHALL enforce exposure between 0.0 and 1.0
4. WHEN persisting performance data, THE Schema_Validator SHALL enforce active_share between 0.0 and 1.0
5. WHEN persisting performance data, THE Schema_Validator SHALL enforce turnover as non-negative float
6. WHEN persisting performance data, THE Schema_Validator SHALL enforce drawdown as non-positive float
7. WHEN persisting performance data, THE Schema_Validator SHALL reject any row with missing required columns
8. THE Schema_Validator SHALL validate all parquet files before writing to disk

### Requirement 16: Data Provenance and Versioning

**User Story:** As an institutional auditor, I want to know exactly which data was used for every decision, so that no result can be manipulated after the fact and all results are reproducible.

#### Acceptance Criteria

1. WHEN Northstar runs, THE Provenance_System SHALL create data manifest file at data/metadata/run_manifest_YYYYMMDD_HHMM.json
2. WHEN creating manifest, THE Provenance_System SHALL include hash of each input file used
3. WHEN creating manifest, THE Provenance_System SHALL include source timestamp for each data file
4. WHEN creating manifest, THE Provenance_System SHALL include schema version for each data file
5. WHEN creating manifest, THE Provenance_System SHALL include code commit hash if git repository available
6. WHEN creating manifest, THE Provenance_System SHALL link manifest to performance_summary.parquet, shadow trades, and risk logs
7. WHEN data changes after a run, THE Provenance_System SHALL flag reproducibility risk in subsequent runs
8. THE Provenance_System SHALL ensure manifests are immutable and cryptographically signed

### Requirement 17: Execution Realism Layer

**User Story:** As a trader, I want backtests to model real execution friction beyond simple costs, so that live trading performance matches backtest expectations.

#### Acceptance Criteria

1. WHEN simulating execution, THE Execution_Model SHALL simulate partial fills based on liquidity constraints
2. WHEN simulating execution, THE Execution_Model SHALL apply market impact scaling with trade volume
3. WHEN simulating execution, THE Execution_Model SHALL model rebalancing delay using T+1 execution instead of T+0
4. WHEN simulating execution, THE Execution_Model SHALL track average slippage per trade
5. WHEN simulating execution, THE Execution_Model SHALL track fill rate percentage
6. WHEN simulating execution, THE Execution_Model SHALL track realized costs versus estimated costs
7. THE Execution_Model SHALL persist execution quality to data/execution/execution_quality.parquet
8. THE Execution_Model SHALL include columns: date, avg_slippage, fill_rate, rebalance_delay, realized_cost

### Requirement 18: Signal Decay Testing

**User Story:** As a quant researcher, I want to detect when strategy signals are degrading over time, so that I can identify overfitting disguised as intelligence.

#### Acceptance Criteria

1. WHEN testing signal decay, THE Signal_Decay_Monitor SHALL track signal strength over time for each strategy
2. WHEN measuring decay, THE Signal_Decay_Monitor SHALL compute correlation between signal strength and forward 4-week returns
3. WHEN measuring decay, THE Signal_Decay_Monitor SHALL compute correlation between signal strength and forward 12-week returns
4. WHEN computing decay rate, THE Signal_Decay_Monitor SHALL measure change in signal-return correlation over rolling windows
5. WHEN decay rate worsens over time, THE Signal_Decay_Monitor SHALL flag strategy as fragile
6. THE Signal_Decay_Monitor SHALL persist results to data/validation/signal_decay.parquet
7. THE Signal_Decay_Monitor SHALL include columns: date, strategy, signal_strength, next_4w_return, next_12w_return, decay_rate
8. THE Signal_Decay_Monitor SHALL alert when decay rate exceeds threshold for 3 consecutive months

### Requirement 19: Strategy Redundancy Monitoring

**User Story:** As a portfolio manager, I want to detect when strategies are highly correlated, so that I don't have secret concentration risk disguised as diversification.

#### Acceptance Criteria

1. WHEN monitoring redundancy, THE Redundancy_Monitor SHALL compute rolling correlation between all strategy pairs
2. WHEN correlation exceeds 0.85 for 6 months, THE Redundancy_Monitor SHALL mark one strategy as replaceable
3. WHEN detecting redundancy, THE Redundancy_Monitor SHALL identify which strategy has lower Sharpe ratio
4. WHEN redundancy is flagged, THE Redundancy_Monitor SHALL recommend capital reallocation
5. THE Redundancy_Monitor SHALL persist results to data/intelligence/strategy_correlation.parquet
6. THE Redundancy_Monitor SHALL include columns: strategy_a, strategy_b, rolling_corr, redundancy_flag, recommended_action
7. THE Redundancy_Monitor SHALL update correlation matrix monthly
8. THE Redundancy_Monitor SHALL visualize correlation heatmap in monthly reports

### Requirement 20: Out-of-Sample Protection Layer

**User Story:** As a systematic trader, I want to test strategies on unseen data, so that I can verify edge is real and not overfit to training period.

#### Acceptance Criteria

1. WHEN testing out-of-sample, THE OOS_Validator SHALL split history into train (1996-2018), validate (2019-2021), and test (2022-2025) periods
2. WHEN computing OOS performance, THE OOS_Validator SHALL require test Sharpe ratio at least 70% of train Sharpe ratio
3. WHEN strategy fails OOS test, THE OOS_Validator SHALL flag strategy as potentially overfit
4. WHEN testing OOS, THE OOS_Validator SHALL ensure no data leakage between periods
5. WHEN testing OOS, THE OOS_Validator SHALL compute performance metrics separately for each period
6. THE OOS_Validator SHALL persist results to data/validation/oos_results.parquet
7. THE OOS_Validator SHALL include columns: strategy, train_sharpe, validate_sharpe, test_sharpe, oos_ratio, pass_flag
8. THE OOS_Validator SHALL require strategies pass OOS test before live deployment

### Requirement 21: Governance and Human Override System

**User Story:** As a fund manager, I want documented human oversight and override capability, so that the system is institutionally credible rather than an uncontrolled black box.

#### Acceptance Criteria

1. WHEN human override occurs, THE Governance_System SHALL log override to data/governance/human_overrides.parquet
2. WHEN logging override, THE Governance_System SHALL track date, override_type, reason, and approved_by
3. WHEN override is requested, THE Governance_System SHALL support emergency pause, exposure cap change, and strategy deactivation types
4. WHEN emergency pause is activated, THE Governance_System SHALL immediately halt all trading and reduce exposure to cash
5. WHEN exposure cap is changed, THE Governance_System SHALL enforce new cap on all subsequent rebalances
6. WHEN strategy is deactivated, THE Governance_System SHALL remove strategy from capital allocation and redistribute capital
7. THE Governance_System SHALL require approval authority verification before executing overrides
8. THE Governance_System SHALL maintain immutable audit trail of all governance actions

### Requirement 22: Explicit No-Trade and No-Signal States

**User Story:** As a risk committee member, I want the system to explicitly declare when it has no edge, so that capital is preserved rather than forced into the market.

#### Acceptance Criteria

1. WHEN regime similarity is below threshold, THE System SHALL enter NO_EDGE state
2. WHEN conflicting tailwinds are detected, THE System SHALL enter NO_EDGE state
3. WHEN beta fabric is unstable, THE System SHALL enter NO_EDGE state
4. WHEN in NO_EDGE state, THE System SHALL cap exposure at maximum 20%
5. WHEN entering NO_EDGE state, THE System SHALL log the specific reason (insufficient regime similarity, conflicting tailwinds, or unstable beta fabric)
6. WHEN in NO_EDGE state, THE System SHALL not generate narratives of confidence
7. WHEN in NO_EDGE state, THE System SHALL maintain defensive positioning with cash and low-volatility assets
8. THE System SHALL track NO_EDGE state transitions in data/intelligence/no_edge_log.parquet

### Requirement 23: Belief Confidence and Uncertainty Tracking

**User Story:** As a portfolio manager, I want to know how confident the system is in its beliefs, so that I can adjust position sizing based on conviction level.

#### Acceptance Criteria

1. WHEN computing regime detection, THE Confidence_System SHALL calculate confidence_score between 0.0 and 1.0
2. WHEN computing strategy tailwinds, THE Confidence_System SHALL calculate confidence_score based on signal stability
3. WHEN computing allocation decisions, THE Confidence_System SHALL calculate confidence_score based on data freshness
4. WHEN confidence_score is below threshold, THE Confidence_System SHALL automatically reduce exposure
5. WHEN confidence_score is below threshold, THE Confidence_System SHALL annotate narratives with uncertainty language
6. WHEN computing confidence, THE Confidence_System SHALL consider regime similarity dispersion, beta drift consistency, signal stability, and data freshness
7. THE Confidence_System SHALL track confidence_score for all major outputs in data/intelligence/belief_confidence.parquet
8. THE Confidence_System SHALL include columns: date, output_type, output_value, confidence_score, confidence_sources

### Requirement 24: Causality Index for Human Readability

**User Story:** As an investor, I want one-line explanations of what drove allocation changes, so that I can quickly understand system behavior without reading technical logs.

#### Acceptance Criteria

1. WHEN month ends, THE Causality_Index SHALL identify top 3 drivers of allocation change
2. WHEN identifying drivers, THE Causality_Index SHALL rank by magnitude of impact on allocation
3. WHEN generating causality index, THE Causality_Index SHALL use human-readable descriptions (e.g., "Liquidity beta ↑ in banks")
4. WHEN storing causality index, THE Causality_Index SHALL persist to data/intelligence/causality_index.parquet
5. WHEN generating monthly reports, THE Report_Generator SHALL include causality index prominently
6. THE Causality_Index SHALL include columns: date, rank, driver_description, impact_magnitude, affected_sectors
7. THE Causality_Index SHALL feed investor letters and dashboard displays
8. THE Causality_Index SHALL provide complete causal chain from macro change to allocation change
