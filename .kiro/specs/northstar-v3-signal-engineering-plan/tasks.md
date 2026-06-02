# Implementation Plan: Northstar V3 Signal Engineering Plan

## Overview

This implementation plan systematically improves the Northstar V3 quantitative equity signal system from baseline IC 0.030 to target IC 0.047+ through 7 phased implementations. The plan addresses critical data integrity issues (PIT leakage), model configuration problems (over-regularization), and regime-specific performance gaps. Each phase includes strict gate enforcement, automated leakage testing, and single-change experiment discipline.

The implementation follows a requirements-first approach with comprehensive PIT audit protocols, feature budget enforcement, and regime-conditional strategies for Indian NSE/BSE equity markets.

## Tasks

### Phase 0: Baseline Stabilization

- [ ] 1. Fix baseline model configuration and critical bugs
  - [ ] 1.1 Revert XGBoost hyperparameters to correct values
    - Set max_depth to 4 (from current over-regularized value)
    - Set min_child_weight to 20 (critical for 150-stock universe)
    - Update configuration file with rationale comments
    - _Requirements: 1.1, 19.1, 19.2_

  - [ ] 1.2 Correct accruals calculation sign inversion
    - Fix formula to (Net_Income - Operating_Cash_Flow) / Total_Assets
    - Add unit tests validating correct sign for known examples
    - Document Indian market behavior (high accruals → higher returns)
    - _Requirements: 1.2, 46.1, 46.3, 46.4_

  - [ ] 1.3 Fix PIT bug in regime_engine.py date alignment
    - Ensure regime classification uses only historical data
    - Fix Nifty_200d_SMA calculation to use data up to current date only
    - Add unit tests validating PIT compliance
    - _Requirements: 1.3, 47.1, 47.2, 47.3, 47.4_

  - [ ] 1.4 Write unit tests for baseline fixes
    - Test XGBoost hyperparameter loading
    - Test accruals calculation with known examples
    - Test regime PIT compliance with time-shifted data
    - _Requirements: 1.2, 1.3, 46.3, 47.3_


- [x] 2. Implement PIT Audit Framework infrastructure
  - [ ] 2.1 Create PITTimestampManager component
    - Implement apply_safety_buffer() with data type mapping
    - Implement validate_timestamps() to check no future dates
    - Implement align_to_trading_calendar() for NSE calendar
    - _Requirements: 2.1, 2.2, 2.3, 2.7_

  - [ ] 2.2 Create PIT audit log database schema
    - Define PITAuditEntry data model with all required fields
    - Create database table for audit entries
    - Implement log_audit_entry() function
    - _Requirements: 2.6, 20.1, 20.2_

  - [ ] 2.3 Write property test for PIT safety buffers
    - **Property 2: PIT Safety Buffers Applied Correctly**
    - **Validates: Requirements 2.3, 2.7, 8.7**
    - Generate random data types and verify correct buffer application
    - _Requirements: 2.3, 2.7_

  - [ ] 2.4 Write property test for PIT round-trip preservation
    - **Property 3: PIT Timestamp Round-Trip Preservation**
    - **Validates: Requirements 1.6**
    - Generate random financial data and verify parse → PIT → parse equivalence
    - _Requirements: 1.6_

- [x] 3. Implement Leakage Test Framework
  - [ ] 3.1 Create LeakageTest component
    - Implement calculate_baseline_ic() with correct PIT alignment
    - Implement calculate_shifted_ic() with 5-day forward shift
    - Implement calculate_ic_ratio() and flag_if_leaking()
    - _Requirements: 14.1, 14.2, 14.3, 14.4_

  - [ ] 3.2 Create leakage test report generator
    - Generate report with IC_ratio for each feature
    - Flag features with IC_ratio >= 1.20
    - Log test execution details and timestamps
    - _Requirements: 14.6, 14.8_

  - [ ] 3.3 Write property test for leakage detection
    - **Property 1: Leakage Test Detects Future Information**
    - **Validates: Requirements 1.5, 2.4, 2.5, 14.4, 14.8**
    - Generate random feature data and verify IC_ratio < 1.20
    - _Requirements: 1.5, 2.4, 14.4_

- [-] 4. Run baseline validation and leakage tests
  - [ ] 4.1 Train baseline model with corrected configuration
    - Load corrected hyperparameters
    - Train on historical data with walk-forward validation
    - Calculate baseline IC and validate >= 0.032
    - _Requirements: 1.4_

  - [ ] 4.2 Execute leakage tests on all existing features
    - Run leakage test for each feature in current feature set
    - Generate leakage report with IC_ratio for all features
    - Verify all features pass (IC_ratio < 1.20)
    - _Requirements: 1.5, 2.5_

  - [ ]* 4.3 Write unit tests for baseline validation
    - Test baseline IC calculation
    - Test leakage test execution
    - Test report generation
    - _Requirements: 1.4, 1.5_

- [ ] 5. Checkpoint - Phase 0 gate validation
  - Verify baseline IC >= 0.032
  - Verify all existing features pass leakage test
  - Ensure all tests pass, ask the user if questions arise.


### Phase 1: Controlled Feature Additions

- [ ] 6. Implement Feature Budget Enforcement system
  - [ ] 6.1 Create FeatureBudgetEnforcer component
    - Implement calculate_budget() as universe_size / 5
    - Implement check_budget_utilization() returning percentage
    - Implement reject_if_exceeded() validation
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

  - [ ] 6.2 Add feature budget logging
    - Log budget utilization after each feature addition
    - Alert when utilization exceeds 80%
    - Reject additions when budget exceeded
    - _Requirements: 3.5, 21.1_

  - [ ]* 6.3 Write property test for feature budget enforcement
    - **Property 4: Feature Budget Enforcement**
    - **Validates: Requirements 3.3, 3.4**
    - Generate random universe sizes and verify budget = N/5
    - _Requirements: 3.3, 3.4_

- [ ] 7. Implement Feature Correlation Management
  - [ ] 7.1 Create correlation matrix calculator
    - Calculate pairwise correlations for all features
    - Update correlation matrix after each addition
    - Store correlation matrix in feature metadata
    - _Requirements: 5.2, 5.5, 22.1, 22.2_

  - [ ] 7.2 Implement correlation-based rejection logic
    - Reject features with correlation > 0.85 with existing features
    - Log warning for correlation > 0.70
    - Document rejection rationale in audit log
    - _Requirements: 4.10, 5.6_

  - [ ]* 7.3 Write property test for correlation rejection
    - **Property 7: Feature Correlation Rejection**
    - **Validates: Requirements 4.10, 5.6**
    - Generate random feature correlations and verify rejection logic
    - _Requirements: 4.10, 5.6_

- [ ] 8. Implement Feature Transformation Pipeline
  - [ ] 8.1 Create FeatureTransformers component
    - Implement WinsorizationTransformer with configurable percentiles
    - Implement LogTransformer for right-skewed distributions
    - Implement RankTransformer for cross-sectional ranking
    - Implement StandardizationTransformer with PIT compliance
    - _Requirements: 15.1, 15.2, 15.5, 15.7_

  - [ ]* 8.2 Write property test for winsorization and rank transformation
    - **Property 23: Winsorization and Rank Transformation**
    - **Validates: Requirements 15.1, 15.7**
    - Generate random feature data and verify transformations
    - _Requirements: 15.1, 15.7_

  - [ ]* 8.3 Write property test for standardization PIT compliance
    - **Property 16: Feature Standardization PIT Compliance**
    - **Validates: Requirements 48.2**
    - Verify training statistics applied to test data only
    - _Requirements: 48.2_


- [ ] 9. Add BAB Beta feature (Experiment 1)
  - [ ] 9.1 Implement BAB beta calculation
    - Calculate 252-day rolling regression beta against Nifty 50
    - Require minimum 126 observations
    - Apply 1-month lag to avoid short-term reversal
    - Apply winsorization at 5th and 95th percentiles
    - _Requirements: 4.1, 24.1, 24.2, 24.3, 24.4, 24.5_

  - [ ] 9.2 Execute experiment with BAB beta
    - Record baseline IC before addition
    - Add BAB beta to feature set
    - Run leakage test (verify IC_ratio < 1.20)
    - Train model and calculate post-change IC
    - Log experiment with IC delta
    - _Requirements: 4.7, 12.2, 12.3, 12.4_

  - [ ]* 9.3 Write unit tests for BAB beta calculation
    - Test beta calculation with known price series
    - Test minimum observation requirement
    - Test lag application
    - _Requirements: 24.1, 24.2, 24.3_

- [ ] 10. Add Amihud Illiquidity feature (Experiment 2)
  - [ ] 10.1 Implement Amihud illiquidity calculation
    - Calculate daily illiquidity as |return| / rupee_volume
    - Aggregate over 21-day rolling windows using median
    - Apply log transformation to reduce skewness
    - Apply winsorization at 1st and 99th percentiles
    - _Requirements: 4.2, 23.1, 23.2, 23.3, 23.4, 23.5_

  - [ ] 10.2 Execute experiment with Amihud illiquidity
    - Record baseline IC
    - Add feature and run leakage test
    - Train and calculate IC delta
    - Log experiment
    - _Requirements: 4.7, 12.2, 12.3, 12.4_

  - [ ]* 10.3 Write unit tests for Amihud illiquidity
    - Test illiquidity calculation with known data
    - Test zero volume handling
    - Test log transformation
    - _Requirements: 23.1, 23.4_

- [ ] 11. Add Piotroski F-Score feature (Experiment 3)
  - [ ] 11.1 Implement Piotroski F-Score calculation
    - Calculate 9 binary signals (ROA, cash flow, margins, leverage, etc.)
    - Sum signals to produce 0-9 score
    - Apply PIT constraints using annual financial dates + 2-day buffer
    - _Requirements: 4.3, 22.1, 22.2, 22.3, 22.4, 22.5, 22.6, 22.7_

  - [ ] 11.2 Execute experiment with Piotroski F-Score
    - Record baseline IC
    - Add feature and run leakage test
    - Train and calculate IC delta
    - Log experiment
    - _Requirements: 4.7, 12.2, 12.3, 12.4_

  - [ ]* 11.3 Write unit tests for Piotroski F-Score
    - Test each of 9 binary signals
    - Test score summation
    - Test PIT buffer application
    - _Requirements: 22.1, 22.2, 22.3, 22.4, 22.5, 22.6_

- [ ] 12. Add 3-month Momentum feature (Experiment 4)
  - [ ] 12.1 Implement momentum calculation
    - Calculate cumulative return from t-4 months to t-1 month
    - Skip most recent month to avoid short-term reversal
    - Use log returns for compounding accuracy
    - Apply winsorization at 1st and 99th percentiles
    - _Requirements: 4.4, 25.1, 25.2, 25.3, 25.4_

  - [ ] 12.2 Execute experiment with momentum
    - Record baseline IC
    - Add feature and run leakage test
    - Train and calculate IC delta
    - Log experiment
    - _Requirements: 4.7, 12.2, 12.3, 12.4_

  - [ ]* 12.3 Write unit tests for momentum calculation
    - Test return calculation with known price series
    - Test 1-month lag application
    - Test log return compounding
    - _Requirements: 25.1, 25.2, 25.4_


- [ ] 13. Add MAX Lottery feature (Experiment 5)
  - [ ] 13.1 Implement MAX lottery calculation
    - Calculate maximum daily return over past 21 trading days
    - Use simple returns (not log returns)
    - Apply winsorization at 99th percentile
    - _Requirements: 4.5, 26.1, 26.3, 26.4_

  - [ ] 13.2 Execute experiment with MAX lottery
    - Record baseline IC
    - Add feature and run leakage test
    - Train and calculate IC delta
    - Log experiment
    - _Requirements: 4.7, 12.2, 12.3, 12.4_

  - [ ]* 13.3 Write unit tests for MAX lottery
    - Test maximum return calculation
    - Test 21-day window
    - Test winsorization
    - _Requirements: 26.1, 26.3, 26.4_

- [ ] 14. Add Earnings Quality Score feature (Experiment 6)
  - [ ] 14.1 Implement earnings quality calculation
    - Calculate accruals as (NI - OCF) / Total_Assets
    - Calculate cash flow to income ratio as OCF / NI
    - Calculate accruals volatility as 8-quarter rolling std
    - Combine with equal weights into composite score
    - Apply winsorization at 5th and 95th percentiles
    - Apply PIT constraints using quarterly dates + 2-day buffer
    - _Requirements: 4.6, 21.1, 21.2, 21.3, 21.4, 21.5, 21.6_

  - [ ] 14.2 Execute experiment with earnings quality
    - Record baseline IC
    - Add feature and run leakage test
    - Train and calculate IC delta
    - Log experiment
    - _Requirements: 4.7, 12.2, 12.3, 12.4_

  - [ ]* 14.3 Write unit tests for earnings quality
    - Test accruals calculation
    - Test cash flow ratio
    - Test composite score
    - _Requirements: 21.1, 21.2, 21.3, 21.4_

  - [ ]* 14.4 Write property test for accruals formula
    - **Property 17: Accruals Calculation Formula**
    - **Validates: Requirements 46.1**
    - Generate random financial statements and verify formula
    - _Requirements: 46.1_

- [ ] 15. Add sector dummy variables
  - [ ] 15.1 Implement sector classification
    - Map stocks to 11 GICS sectors using Screener data
    - Create one-hot encoded dummy variables
    - Handle missing sectors with 'Other' category
    - _Requirements: 4.9, 36.1, 36.2, 36.3, 36.4, 36.5_

  - [ ] 15.2 Add sector dummies to feature set
    - Add 11 sector dummy features
    - Update feature budget accounting
    - Train model with sector dummies
    - _Requirements: 36.3_

  - [ ]* 15.3 Write unit tests for sector classification
    - Test sector mapping
    - Test one-hot encoding
    - Test missing sector handling
    - _Requirements: 36.4, 36.5_

- [ ] 16. Checkpoint - Phase 1 gate validation
  - Verify IC >= 0.037
  - Verify all new features pass leakage test
  - Verify feature budget not exceeded (should be <= 32 for 150 stocks)
  - Ensure all tests pass, ask the user if questions arise.


### Phase 2: Bulk Deal Integration

- [ ] 17. Implement Bulk Deal Buyer Classification System
  - [ ] 17.1 Create BuyerNameNormalizer component
    - Implement remove_special_chars() for name cleaning
    - Implement standardize_abbreviations() for common patterns
    - Implement lowercase_and_strip() for normalization
    - _Requirements: 20.2_

  - [ ] 17.2 Create FuzzyMatcher component
    - Implement calculate_levenshtein_distance() for string similarity
    - Implement calculate_similarity_score() returning 0-1 scale
    - Implement match_to_category() with 85% threshold
    - Load category patterns for FII, DII, Promoter, Institutional, Retail
    - _Requirements: 6.1, 20.1, 20.2, 20.3, 20.4_

  - [ ] 17.3 Create buyer classification lookup table
    - Define 6 categories: FII, DII, Promoter, Institutional, Retail, Unknown
    - Create pattern database for each category
    - Support manual overrides for edge cases
    - _Requirements: 20.1, 20.5_

  - [ ]* 17.4 Write property test for bulk deal buyer classification
    - **Property 8: Bulk Deal Buyer Classification**
    - **Validates: Requirements 6.1, 20.3, 20.4**
    - Generate random buyer names and verify classification logic
    - _Requirements: 6.1, 20.3, 20.4_

  - [ ]* 17.5 Write unit tests for fuzzy matching
    - Test Levenshtein distance calculation
    - Test similarity threshold (85%)
    - Test Unknown category assignment
    - _Requirements: 20.2, 20.3, 20.4_

- [ ] 18. Implement Bulk Deal Feature Engineering
  - [ ] 18.1 Create BulkDealAggregator component
    - Implement normalize_by_free_float() using Screener shareholding data
    - Implement aggregate_by_category() over 21-day windows
    - Implement calculate_rolling_features() for 4 bulk deal features
    - _Requirements: 6.2, 6.7, 20.6, 20.7_

  - [ ] 18.2 Calculate 4 bulk deal features
    - Net institutional buying (FII + DII + Institutional)
    - Promoter buying
    - FII net flow
    - DII net flow
    - All normalized by free float and aggregated over 21 days
    - _Requirements: 6.3_

  - [ ] 18.3 Implement free float normalization
    - Source free float from Screener shareholding data
    - Use 50% default when data missing
    - Apply PIT constraints using shareholding date + 2-day buffer
    - Update quarterly
    - _Requirements: 37.1, 37.2, 37.3, 37.4, 37.5_

  - [ ]* 18.4 Write property test for bulk deal normalization
    - **Property 9: Bulk Deal Normalization and Aggregation**
    - **Validates: Requirements 6.2, 6.7**
    - Generate random bulk deals and verify normalization and aggregation
    - _Requirements: 6.2, 6.7_

  - [ ]* 18.5 Write unit tests for bulk deal features
    - Test free float normalization
    - Test 21-day aggregation
    - Test missing data handling
    - _Requirements: 6.2, 6.7, 37.2, 37.3_


- [ ] 19. Implement Survivorship Bias Mitigation
  - [ ] 19.1 Create delisting event table
    - Define schema with date, stock, reason, classification (forced/voluntary)
    - Populate with historical delisting events
    - Classify each delisting as forced or voluntary
    - _Requirements: 32.4, 32.5_

  - [ ] 19.2 Implement delisting return treatment
    - Apply -100% return for forced delistings (fraud, suspension, insolvency)
    - Use actual last price or buyout premium for voluntary delistings
    - Include delisted stocks in analysis up to delisting date
    - _Requirements: 32.1, 32.2, 32.3_

  - [ ] 19.3 Apply survivorship filter to bulk deals
    - Flag bulk deals from delisted stocks
    - Exclude from feature calculation if appropriate
    - _Requirements: 6.4, 32.6_

  - [ ]* 19.4 Write property test for delisting return treatment
    - **Property 15: Delisting Return Treatment**
    - **Validates: Requirements 32.2, 32.3**
    - Generate random delistings and verify correct return application
    - _Requirements: 32.2, 32.3_

  - [ ]* 19.5 Write unit tests for survivorship bias
    - Test forced delisting return (-100%)
    - Test voluntary delisting return (actual price)
    - Test delisting classification
    - _Requirements: 32.2, 32.3, 32.5_

- [ ] 20. Add bulk deal features and validate
  - [ ] 20.1 Execute experiment with bulk deal features
    - Record baseline IC
    - Add 4 bulk deal features to feature set
    - Run leakage test on each feature
    - Train model and calculate IC delta
    - Log experiment
    - _Requirements: 6.5, 12.2, 12.3, 12.4_

  - [ ] 20.2 Validate PIT compliance for bulk deals
    - Verify trade date is public availability date (no buffer needed)
    - Run leakage test and verify IC_ratio < 1.20
    - Document in PIT audit log
    - _Requirements: 6.5_

  - [ ]* 20.3 Write unit tests for bulk deal integration
    - Test feature calculation end-to-end
    - Test PIT compliance
    - Test leakage test execution
    - _Requirements: 6.5_

- [ ] 21. Checkpoint - Phase 2 gate validation
  - Verify IC >= 0.039
  - Verify all bulk deal features pass leakage test
  - Verify feature budget not exceeded
  - Ensure all tests pass, ask the user if questions arise.


### Phase 3: Regime Overlay Implementation

- [ ] 22. Implement 2-Axis Regime Classification Framework
  - [ ] 22.1 Create RegimeClassificationEngine component
    - Implement VolatilityAxis with India VIX threshold (20)
    - Implement TrendAxis with Nifty 200-day SMA calculation
    - Implement RegimeClassifier with 4-regime logic
    - Implement regime transition logging
    - _Requirements: 7.1, 7.2, 7.7, 28.5, 28.6, 28.7_

  - [ ] 22.2 Implement regime classification logic
    - risk_on_calm: VIX <= 20 AND Nifty > 200d_SMA
    - risk_on_volatile: VIX > 20 AND Nifty > 200d_SMA
    - risk_off_calm: VIX <= 20 AND Nifty < 200d_SMA
    - risk_off_volatile: VIX > 20 AND Nifty < 200d_SMA
    - _Requirements: 7.3, 7.4, 28.1, 28.2, 28.3, 28.4_

  - [ ] 22.3 Integrate India VIX and Nifty data sources
    - Load India VIX daily history from NSE indices API
    - Calculate Nifty 200-day SMA using 200 trading days
    - Update regime classification daily
    - _Requirements: 16.2, 28.5, 28.6_

  - [ ]* 22.4 Write property test for regime classification
    - **Property 6: Regime Classification Logic**
    - **Validates: Requirements 7.3, 7.4, 28.1, 28.2, 28.3, 28.4**
    - Generate random VIX and Nifty data and verify correct regime assignment
    - _Requirements: 7.3, 7.4, 28.1, 28.2, 28.3, 28.4_

  - [ ]* 22.5 Write property test for regime PIT compliance
    - **Property 5: Regime Classification PIT Compliance**
    - **Validates: Requirements 1.3, 47.4**
    - Verify regime uses only historical data for any date
    - _Requirements: 1.3, 47.4_

  - [ ]* 22.6 Write unit tests for regime classification
    - Test VIX threshold (exactly 20)
    - Test SMA calculation
    - Test regime transition logging
    - _Requirements: 7.3, 7.4, 28.5_

- [ ] 23. Implement Regime-Conditional Feature Weights
  - [ ] 23.1 Create RegimeWeightManager component
    - Implement load_regime_weights() from configuration
    - Implement apply_conditional_weights() to XGBoost sample weights
    - Support separate weight vectors per regime
    - _Requirements: 7.5_

  - [ ] 23.2 Train regime-conditional model
    - Train XGBoost with regime-conditional sample weights
    - Use data after 2016 only (reserve 2013-2016 for hold-out)
    - Calculate IC separately for each regime
    - _Requirements: 7.5, 7A.2_

  - [ ]* 23.3 Write unit tests for regime weights
    - Test weight loading from configuration
    - Test weight application to samples
    - Test regime-specific training
    - _Requirements: 7.5_

- [ ] 24. Implement Regime Hold-Out Validation
  - [ ] 24.1 Reserve 2013-2016 as hold-out period
    - Exclude 2013-2016 from regime weight training
    - Train regime weights using data after 2016 only
    - _Requirements: 7A.1, 7A.2_

  - [ ] 24.2 Validate regime weights on hold-out period
    - Calculate IC on 2013-2016 hold-out period
    - Compare hold-out IC to training period IC
    - Flag if hold-out IC degrades by > 0.010
    - Document hold-out validation results
    - _Requirements: 7A.3, 7A.4, 7A.5, 7A.6_

  - [ ]* 24.3 Write unit tests for hold-out validation
    - Test hold-out period exclusion
    - Test IC comparison logic
    - Test overfitting flag
    - _Requirements: 7A.3, 7A.4_


- [ ] 25. Replace 14-label regime system with 4-regime system
  - [ ] 25.1 Remove old regime classification code
    - Remove 14-label regime logic from codebase
    - Update all references to use new 4-regime system
    - Update configuration files
    - _Requirements: 7.7_

  - [ ] 25.2 Validate regime performance
    - Calculate IC for each of 4 regimes
    - Verify all regime IC > 0.010
    - Generate regime performance report
    - _Requirements: 7.8, 17.3_

  - [ ]* 25.3 Write unit tests for regime system replacement
    - Test 4-regime system integration
    - Test IC calculation by regime
    - Test performance reporting
    - _Requirements: 7.7, 7.8_

- [ ] 26. Checkpoint - Phase 3 gate validation
  - Verify IC >= 0.040
  - Verify all regime IC > 0.010 (critical gate)
  - Verify hold-out validation passed
  - Ensure all tests pass, ask the user if questions arise.

### Phase 4: Earnings Surprise Signal

- [ ] 27. Implement NSE Earnings Announcement Scraper
  - [ ] 27.1 Create NSE announcement scraper
    - Scrape earnings announcement dates from NSE corporate announcements page
    - Parse dates in DD-MMM-YYYY format
    - Store in structured database table
    - Update daily
    - _Requirements: 8.1, 16.1, 38.1, 38.2, 38.3, 38.5_

  - [ ] 27.2 Implement scraping error handling
    - Log errors when scraping fails
    - Use fallback: financial statement date + 30 days
    - Validate announcement dates not in future
    - _Requirements: 38.4, 38.6_

  - [ ]* 27.3 Write unit tests for announcement scraper
    - Test date parsing (DD-MMM-YYYY format)
    - Test fallback logic
    - Test future date validation
    - _Requirements: 38.2, 38.4, 38.6_

- [ ] 28. Implement Standardized Unexpected Earnings (SUE) Calculation
  - [ ] 28.1 Create SUE calculator component
    - Calculate earnings surprise as actual EPS - expected EPS
    - Use seasonal random-walk model (EPS from 4 quarters ago)
    - Normalize by 8-quarter rolling standard deviation
    - Apply winsorization at 5th and 95th percentiles
    - _Requirements: 8.2, 8.3, 27.1, 27.2, 27.3, 27.4, 27.5_

  - [ ] 28.2 Apply PIT constraints to SUE
    - Use NSE announcement date + 1-day buffer
    - Fallback to statement date + 30 days if announcement missing
    - Run leakage test to verify IC_ratio < 1.20
    - _Requirements: 8.4, 8.7, 27.6, 27.7_

  - [ ]* 28.3 Write unit tests for SUE calculation
    - Test seasonal random-walk expectation
    - Test normalization by rolling std
    - Test PIT buffer application
    - _Requirements: 27.1, 27.2, 27.3, 27.6, 27.7_


- [ ] 29. Evaluate Dual-Horizon Architecture (Conditional)
  - [ ] 29.1 Implement dual-horizon model training
    - Train separate XGBoost models for 5-day and 21-day forward returns
    - Calculate IC separately for each horizon
    - _Requirements: 8.5, 8.8, 39.1, 39.2_

  - [ ] 29.2 Implement regime-conditional alpha blending
    - Create RegimeConditionalBlender component
    - Set alpha weights: risk_on_volatile=0.80, risk_on_calm=0.65, risk_off_calm=0.55, risk_off_volatile=0.50
    - Blend predictions: alpha * pred_5d + (1-alpha) * pred_21d
    - _Requirements: 39.3, 39.4, 39.5, 39.6, 39.7_

  - [ ] 29.3 Evaluate Sharpe improvement gate
    - Calculate baseline Sharpe (single 5-day model)
    - Calculate ensemble Sharpe (dual-horizon)
    - If improvement >= 0.05, implement dual-horizon; else retain single model
    - Document decision rationale
    - _Requirements: 8A.1, 8A.2, 8A.3, 8A.4, 8A.5, 39.8, 39.9_

  - [ ]* 29.4 Write property test for dual-horizon alpha blending
    - **Property 10: Dual-Horizon Alpha Blending**
    - **Validates: Requirements 39.4, 39.5, 39.6, 39.7**
    - Generate random predictions and verify regime-conditional blending
    - _Requirements: 39.4, 39.5, 39.6, 39.7_

  - [ ]* 29.5 Write unit tests for dual-horizon architecture
    - Test separate model training
    - Test alpha weight loading
    - Test Sharpe gate evaluation
    - _Requirements: 8A.1, 8A.2, 8A.3, 39.1, 39.2_

- [ ] 30. Add SUE feature and validate
  - [ ] 30.1 Execute experiment with SUE feature
    - Record baseline IC
    - Add SUE to feature set
    - Run leakage test
    - Train model (single or dual-horizon based on gate)
    - Calculate IC delta
    - Log experiment
    - _Requirements: 12.2, 12.3, 12.4_

  - [ ]* 30.2 Write unit tests for SUE integration
    - Test SUE feature calculation end-to-end
    - Test PIT compliance
    - Test leakage test execution
    - _Requirements: 8.4_

- [ ] 31. Checkpoint - Phase 4 gate validation
  - Verify IC >= 0.041
  - Verify SUE passes leakage test
  - Document dual-horizon decision (implemented or not)
  - Ensure all tests pass, ask the user if questions arise.


### Phase 5: Universe Expansion

- [ ] 32. Build Point-In-Time Universe Membership Table
  - [ ] 32.1 Create PIT universe membership schema
    - Define table with stock, date, in_universe, reason fields
    - Track index additions and deletions with timestamps
    - Support quarterly rebalancing
    - _Requirements: 9.2, 31.4_

  - [ ] 32.2 Integrate NSE historical index compositions
    - Load historical index membership from NSE historical data
    - Parse addition/deletion dates
    - Populate PIT universe table
    - _Requirements: 16.3_

  - [ ]* 32.3 Write unit tests for PIT universe table
    - Test membership tracking
    - Test addition/deletion recording
    - Test quarterly rebalancing
    - _Requirements: 9.2, 31.4_

- [ ] 33. Implement Universe Liquidity Filtering
  - [ ] 33.1 Create liquidity filter component
    - Calculate ADT as 21-day average of daily rupee volume
    - Apply minimum threshold of Rs 2 crore
    - Exclude stocks with < 252 trading days of history
    - Recalculate quarterly
    - _Requirements: 9.3, 9.6, 31.1, 31.2, 31.3, 31.5_

  - [ ] 33.2 Validate data quality for expanded universe
    - Validate price data has no gaps > 5 trading days
    - Validate financial data has no duplicates
    - Validate features have < 20% missing values
    - _Requirements: 45.1, 45.2, 45.3_

  - [ ]* 33.3 Write property test for data quality validation
    - **Property 18: Data Quality Validation**
    - **Validates: Requirements 45.1, 45.6**
    - Generate random price data and verify gap detection
    - _Requirements: 45.1, 45.6_

  - [ ]* 33.4 Write unit tests for liquidity filtering
    - Test ADT calculation
    - Test threshold application (Rs 2 crore)
    - Test history requirement (252 days)
    - _Requirements: 31.1, 31.2, 31.5_

- [ ] 34. Expand universe from 150 to 300 stocks
  - [ ] 34.1 Update universe configuration
    - Set universe size to 300 stocks
    - Update feature budget to 45 (300 / 5)
    - Apply liquidity filters to select 300 stocks
    - _Requirements: 9.1, 9.4_

  - [ ] 34.2 Retrain model with expanded universe
    - Train XGBoost with 300-stock universe
    - Validate feature budget not exceeded (45 max)
    - Calculate IC on expanded universe
    - _Requirements: 9.4_

  - [ ]* 34.3 Write unit tests for universe expansion
    - Test universe size update
    - Test feature budget recalculation
    - Test liquidity filter application
    - _Requirements: 9.1, 9.4_

- [ ] 35. Checkpoint - Phase 5 gate validation
  - Verify IC >= 0.043
  - Verify universe contains 300 stocks
  - Verify feature budget = 45 and not exceeded
  - Ensure all tests pass, ask the user if questions arise.


### Phase 6: Advanced Signal Integration

- [ ] 36. Integrate Trendlyne Consensus Data (Conditional)
  - [ ] 36.1 Implement Trendlyne API integration
    - Integrate Trendlyne API with subscription credentials
    - Load earnings estimates and analyst revisions
    - Apply PIT constraints using estimate revision dates
    - _Requirements: 10.1, 16.6, 29.1, 29.3_

  - [ ] 36.2 Calculate consensus revision diffusion
    - Calculate percentage of analysts raising estimates over past 30 days
    - Apply winsorization at 5th and 95th percentiles
    - Run leakage test to verify IC_ratio < 1.20
    - _Requirements: 10.2, 10.5, 29.2, 29.4_

  - [ ]* 36.3 Write unit tests for Trendlyne integration
    - Test API authentication
    - Test revision diffusion calculation
    - Test PIT compliance
    - _Requirements: 29.1, 29.2, 29.3_

- [ ] 37. Add Promoter Pledge Change Signal
  - [ ] 37.1 Implement promoter pledge calculation
    - Calculate quarterly delta in pledge percentage
    - Source data from Screener quarterly shareholding
    - Apply PIT constraints using shareholding date + 2-day buffer
    - Apply winsorization at 5th and 95th percentiles
    - Impute zero change when data missing
    - _Requirements: 10.3, 30.1, 30.2, 30.3, 30.4, 30.5_

  - [ ] 37.2 Execute experiment with promoter pledge
    - Record baseline IC
    - Add promoter pledge change to feature set
    - Run leakage test
    - Train and calculate IC delta
    - Log experiment
    - _Requirements: 12.2, 12.3, 12.4_

  - [ ]* 37.3 Write unit tests for promoter pledge
    - Test quarterly delta calculation
    - Test PIT buffer application
    - Test missing data imputation
    - _Requirements: 30.1, 30.3, 30.5_

- [ ] 38. Add MAX5 Lottery Feature
  - [ ] 38.1 Implement MAX5 calculation
    - Calculate maximum daily return over past 5 trading days
    - Use simple returns (not log returns)
    - Apply winsorization at 99th percentile
    - _Requirements: 10.4, 26.2, 26.3, 26.4_

  - [ ] 38.2 Execute experiment with MAX5
    - Record baseline IC
    - Add MAX5 to feature set
    - Run leakage test
    - Train and calculate IC delta
    - Log experiment
    - _Requirements: 12.2, 12.3, 12.4_

  - [ ]* 38.3 Write unit tests for MAX5
    - Test 5-day maximum calculation
    - Test simple return usage
    - Test winsorization
    - _Requirements: 26.2, 26.3, 26.4_

- [ ] 39. Validate advanced signal integration
  - [ ] 39.1 Execute experiments for all Phase 6 features
    - Add Trendlyne consensus (if implemented)
    - Add promoter pledge change
    - Add MAX5
    - Run leakage tests for all features
    - Calculate cumulative IC improvement
    - _Requirements: 10.5, 10.6_

  - [ ]* 39.2 Write integration tests for Phase 6
    - Test all features together
    - Test feature budget compliance
    - Test correlation matrix updates
    - _Requirements: 10.6_

- [ ] 40. Checkpoint - Phase 6 gate validation
  - Verify IC >= 0.045
  - Verify all Phase 6 features pass leakage test
  - Verify feature budget not exceeded
  - Ensure all tests pass, ask the user if questions arise.


### Phase 7: Sequence Model Ensemble (Conditional)

- [ ] 41. Implement Temporal Convolutional Network (TCN)
  - [ ] 41.1 Create TCN model architecture
    - Implement dilated causal convolutions with dilation rates [1, 2, 4, 8]
    - Implement 4 residual blocks with 64 filters each
    - Apply dropout of 0.2 for regularization
    - Use 60-day lookback windows
    - _Requirements: 11.1, 40.1, 40.2, 40.3, 40.4_

  - [ ] 41.2 Implement TCN training pipeline
    - Create SequenceDataGenerator for 60-day windows
    - Train using Adam optimizer with learning rate 0.001
    - Apply early stopping with patience of 10 epochs
    - _Requirements: 40.5, 40.6_

  - [ ]* 41.3 Write unit tests for TCN architecture
    - Test dilated convolution layers
    - Test residual blocks
    - Test sequence data generation
    - _Requirements: 40.1, 40.2, 40.3_

- [ ] 42. Implement Transformer Model
  - [ ] 42.1 Create Transformer architecture
    - Implement positional encoding for sequences
    - Implement multi-head attention with 4 heads
    - Implement 2 encoder layers with 128 hidden dimensions
    - Apply dropout of 0.2 for regularization
    - Use 60-day lookback windows
    - _Requirements: 11.2, 41.1, 41.2, 41.3, 41.4, 41.5_

  - [ ] 42.2 Implement Transformer training pipeline
    - Create sequence data generator
    - Train using Adam optimizer with learning rate 0.0001
    - Apply early stopping
    - _Requirements: 41.6_

  - [ ]* 42.3 Write unit tests for Transformer architecture
    - Test positional encoding
    - Test multi-head attention
    - Test encoder layers
    - _Requirements: 41.1, 41.2, 41.3_

- [ ] 43. Implement Model Ensemble Strategy
  - [ ] 43.1 Create EnsembleBlender component
    - Blend XGBoost (60%) with sequence model (40%)
    - Validate predictions not perfectly correlated
    - Calculate ensemble IC
    - _Requirements: 11.3, 42.1, 42.2, 42.5_

  - [ ] 43.2 Evaluate IC improvement gate
    - Calculate XGBoost baseline IC
    - Calculate ensemble IC
    - If improvement >= 0.003, deploy ensemble; else retain XGBoost only
    - Document decision rationale
    - _Requirements: 11.4, 11.5, 42.3, 42.4_

  - [ ]* 43.3 Write unit tests for ensemble strategy
    - Test weight blending (60/40)
    - Test correlation validation
    - Test IC gate evaluation
    - _Requirements: 42.1, 42.2, 42.4, 42.5_

- [ ] 44. Train and evaluate sequence models
  - [ ] 44.1 Train TCN and Transformer models
    - Prepare 60-day sequence data
    - Train both architectures
    - Generate predictions on test set
    - _Requirements: 11.7_

  - [ ] 44.2 Evaluate ensemble performance
    - Calculate ensemble IC
    - Compare to XGBoost baseline
    - Evaluate gate: IC improvement >= 0.003
    - Make deployment decision
    - _Requirements: 11.4, 11.5, 11.6_

  - [ ]* 44.3 Write integration tests for sequence models
    - Test end-to-end training pipeline
    - Test ensemble prediction generation
    - Test gate evaluation
    - _Requirements: 11.4, 11.6_

- [ ] 45. Checkpoint - Phase 7 gate validation
  - Verify IC >= 0.047 (final target)
  - Document sequence model decision (deployed or not)
  - Verify all regime IC > 0.010
  - Ensure all tests pass, ask the user if questions arise.


### Cross-Cutting: Experiment Tracking and Gate Enforcement

- [ ] 46. Implement Experiment Tracking System
  - [ ] 46.1 Create ExperimentLogger component
    - Implement log_experiment() with before/after IC
    - Implement record_baseline_ic() and record_post_change_ic()
    - Implement calculate_ic_delta()
    - Store experiments in database with timestamps
    - _Requirements: 12.2, 12.3, 12.4, 12.5_

  - [ ] 46.2 Implement single-change validation
    - Validate exactly one change per experiment
    - Revert change if IC delta is negative
    - Use identical train/test splits for fair comparison
    - _Requirements: 12.1, 12.6, 12.7_

  - [ ]* 46.3 Write property test for experiment discipline
    - **Property 11: Experiment Single-Change Discipline**
    - **Validates: Requirements 12.1, 12.6**
    - Verify single change and revert on negative delta
    - _Requirements: 12.1, 12.6_

  - [ ]* 46.4 Write unit tests for experiment tracking
    - Test experiment logging
    - Test IC delta calculation
    - Test revert logic
    - _Requirements: 12.2, 12.3, 12.4, 12.6_

- [ ] 47. Implement Gate Enforcement System
  - [ ] 47.1 Create GateEnforcer component
    - Define phase gate thresholds (0.032, 0.037, 0.039, 0.040, 0.041, 0.043, 0.045, 0.047)
    - Implement evaluate_phase_gate() with IC and regime checks
    - Implement halt_if_failed() to stop progression
    - Implement generate_diagnostic_report() for failures
    - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.6_

  - [ ] 47.2 Implement gate evaluation logic
    - Check primary IC against phase threshold
    - Check regime IC > 0.010 for Phase 3+
    - Log gate results with pass/fail status
    - Prevent feature additions when gate failed
    - _Requirements: 13.1, 13.2, 13.5_

  - [ ]* 47.3 Write property test for gate enforcement
    - **Property 12: Gate Enforcement Halts Progression**
    - **Validates: Requirements 13.2**
    - Generate random IC values and verify halt logic
    - _Requirements: 13.2_

  - [ ]* 47.4 Write unit tests for gate enforcement
    - Test threshold evaluation
    - Test halt logic
    - Test diagnostic report generation
    - _Requirements: 13.1, 13.2, 13.6_


### Cross-Cutting: Performance Validation and Reporting

- [ ] 48. Implement Walk-Forward Validation Pipeline
  - [ ] 48.1 Create WalkForwardValidator component
    - Implement generate_folds() with 24-month train, 3-month test windows
    - Implement train_fold() and validate_fold()
    - Advance window by 3 months for each fold
    - Maintain temporal ordering with no look-ahead bias
    - _Requirements: 17.8, 33.1, 33.2, 33.3, 33.4, 33.7_

  - [ ] 48.2 Implement IC calculation and aggregation
    - Calculate IC as Spearman rank correlation
    - Calculate IC separately for each test window
    - Aggregate IC across all test windows
    - _Requirements: 17.1, 33.5, 33.6_

  - [ ]* 48.3 Write property test for IC calculation
    - **Property 13: IC Calculation Formula**
    - **Validates: Requirements 17.1**
    - Generate random predictions and returns, verify Spearman correlation
    - _Requirements: 17.1_

  - [ ]* 48.4 Write unit tests for walk-forward validation
    - Test fold generation
    - Test temporal ordering
    - Test IC aggregation
    - _Requirements: 33.1, 33.2, 33.3, 33.7_

- [ ] 49. Implement Performance Reporting System
  - [ ] 49.1 Create PerformanceEvaluator component
    - Implement calculate_ic() for overall and by-regime
    - Implement calculate_sharpe() with 25 bps transaction costs
    - Implement calculate_turnover() as portfolio change percentage
    - Calculate IC by sector for sector-specific analysis
    - Generate monthly IC time series for stability assessment
    - _Requirements: 17.1, 17.2, 17.3, 17.4, 17.5, 17.9_

  - [ ] 49.2 Implement transaction cost modeling
    - Apply 25 basis points per round-trip trade
    - Calculate net returns as gross returns minus costs
    - Assume monthly rebalancing frequency
    - _Requirements: 35.1, 35.2, 35.3, 35.4, 35.5_

  - [ ]* 49.3 Write unit tests for performance metrics
    - Test IC calculation
    - Test Sharpe ratio with transaction costs
    - Test turnover calculation
    - _Requirements: 17.1, 17.2, 35.1, 35.4_

- [ ] 50. Implement SHAP Feature Importance Validation
  - [ ] 50.1 Create SHAP analyzer component
    - Calculate SHAP values for all features
    - Calculate mean absolute SHAP as importance metric
    - Flag features with mean |SHAP| < 0.01 as low-importance
    - Generate SHAP summary plots for top 20 features
    - Validate SHAP ranking aligns with IC contribution
    - _Requirements: 5.3, 5.4, 34.1, 34.2, 34.3, 34.4, 34.5_

  - [ ]* 50.2 Write unit tests for SHAP analysis
    - Test SHAP value calculation
    - Test importance metric
    - Test low-importance flagging
    - _Requirements: 34.1, 34.2, 34.3_


### Cross-Cutting: Risk Monitoring and Mitigation

- [ ] 51. Implement Risk Register and Monitoring Framework
  - [ ] 51.1 Create RiskRegister component
    - Define 8 failure modes: PIT leakage, correlation, regime underperformance, overfitting, IC degradation, data staleness, train/test gap, survivorship bias
    - Implement track_risk_event() with severity levels
    - Implement log_mitigation_actions()
    - Implement generate_risk_reports() for weekly summaries
    - _Requirements: 18.1, 18.6, 18.7_

  - [ ] 51.2 Implement automated mitigation protocols
    - LeakageMitigationProtocol: detect and remove leaking features
    - CorrelationMitigationProtocol: reject redundant features
    - RegimePerformanceMitigationProtocol: adjust regime weights
    - OverfittingMitigationProtocol: remove low-importance features
    - _Requirements: 18.2, 18.3, 18.4, 18.5_

  - [ ] 51.3 Implement IC degradation monitoring
    - Monitor IC changes between phases
    - Trigger diagnostic if IC drops > 0.005
    - Alert on regime IC < 0.010
    - _Requirements: 18.8_

  - [ ]* 51.4 Write unit tests for risk monitoring
    - Test risk event logging
    - Test mitigation protocol execution
    - Test alert triggering
    - _Requirements: 18.1, 18.2, 18.6_

- [ ] 52. Implement Data Quality Validation System
  - [ ] 52.1 Create DataQualityValidator component
    - Validate price data gaps <= 5 trading days
    - Validate no duplicate financial records
    - Validate features have < 20% missing values
    - Validate all timestamps in the past
    - Validate all numeric features are finite (no NaN/Inf)
    - _Requirements: 45.1, 45.2, 45.3, 45.5, 45.6_

  - [ ] 52.2 Implement validation error handling
    - Log validation failures
    - Halt model training on critical failures
    - Generate weekly data quality reports
    - _Requirements: 45.4, 45.7_

  - [ ]* 52.3 Write unit tests for data quality validation
    - Test gap detection
    - Test duplicate detection
    - Test missing value percentage
    - Test timestamp validation
    - _Requirements: 45.1, 45.2, 45.3, 45.5, 45.6_

- [ ] 53. Implement Missing Value Imputation Strategy
  - [ ] 53.1 Create imputation pipeline
    - Apply forward-fill using most recent non-missing value
    - Apply median imputation using training data median
    - Calculate imputation statistics from training data only
    - Log percentage of imputed values per feature
    - Flag features with > 20% missing values
    - _Requirements: 15.6, 49.1, 49.2, 49.3, 49.4, 49.5_

  - [ ]* 53.2 Write unit tests for imputation
    - Test forward-fill logic
    - Test median imputation
    - Test training-only statistics
    - Test missing value flagging
    - _Requirements: 49.1, 49.2, 49.3, 49.5_


### Cross-Cutting: Configuration Management and Versioning

- [ ] 54. Implement Configuration Management System
  - [ ] 54.1 Create configuration schema and validation
    - Define YAML schema for all configuration parameters
    - Implement validate_schema() to check required fields and types
    - Reject invalid configurations before execution
    - _Requirements: 43.6, 19.1_

  - [ ] 54.2 Create ConfigVersionControl component
    - Implement tag_version() with unique version identifiers
    - Implement commit_changes() with timestamps and descriptions
    - Implement rollback_to_version() for configuration recovery
    - Store all hyperparameters in version-controlled files
    - _Requirements: 43.1, 43.2, 43.3, 43.5_

  - [ ] 54.3 Implement changelog management
    - Log all configuration changes with timestamps
    - Maintain changelog documenting modifications
    - Enable configuration comparison between versions
    - _Requirements: 43.4_

  - [ ]* 54.4 Write property test for configuration validation
    - **Property 19: Configuration Schema Validation**
    - **Validates: Requirements 43.6**
    - Generate random configurations and verify schema validation
    - _Requirements: 43.6_

  - [ ]* 54.5 Write unit tests for configuration management
    - Test schema validation
    - Test version tagging
    - Test rollback functionality
    - _Requirements: 43.1, 43.2, 43.5, 43.6_

- [ ] 55. Implement Diagnostic Reporting System
  - [ ] 55.1 Create diagnostic report generators
    - Generate daily reports with IC, Sharpe, turnover
    - Generate weekly feature importance reports with SHAP
    - Generate monthly regime performance reports
    - Generate quarterly performance review with YoY comparisons
    - _Requirements: 44.1, 44.2, 44.3, 44.7_

  - [ ] 55.2 Implement alert system
    - Alert on IC degradation > 0.005
    - Alert on regime IC < 0.010
    - Log alerts with timestamps and severity
    - _Requirements: 44.4, 44.5, 44.6_

  - [ ]* 55.3 Write unit tests for diagnostic reporting
    - Test report generation
    - Test alert triggering
    - Test severity classification
    - _Requirements: 44.1, 44.4, 44.5_


### Cross-Cutting: Parser Round-Trip Properties

- [ ] 56. Implement and test data parsers with round-trip properties
  - [ ] 56.1 Implement NSE announcement date parser
    - Parse DD-MMM-YYYY format dates from NSE pages
    - Implement pretty printer to format dates back to DD-MMM-YYYY
    - Ensure round-trip: parse → print → parse produces equivalent date
    - _Requirements: 38.1, 38.2_

  - [ ] 56.2 Implement financial data parser
    - Parse quarterly/annual financial statements from Screener CSV
    - Implement pretty printer to format back to valid CSV
    - Ensure round-trip: parse → print → parse produces equivalent values
    - _Requirements: 16.4_

  - [ ] 56.3 Implement bulk deal parser
    - Parse bulk deal transaction data from NSE/BSE
    - Implement pretty printer to format back to structured format
    - Ensure round-trip: parse → print → parse produces equivalent transactions
    - _Requirements: 16.5_

  - [ ]* 56.4 Write property test for parser round-trip properties
    - **Property 24: Parser Round-Trip Properties**
    - **Validates: Requirements from Notes section**
    - Generate random dates, financial data, bulk deals
    - Verify parse → print → parse equivalence for all
    - _Requirements: Notes section (Parser and Serializer Requirements)_

  - [ ]* 56.5 Write unit tests for parsers
    - Test date parsing (DD-MMM-YYYY)
    - Test financial data parsing
    - Test bulk deal parsing
    - Test error handling for invalid inputs
    - _Requirements: 38.2_

### Final Validation and Deployment

- [ ] 57. Execute final success criteria validation
  - [ ] 57.1 Validate final performance metrics
    - Verify IC >= 0.047 (primary target)
    - Verify Sharpe ratio > 0.25 after 25 bps costs
    - Verify all regime IC > 0.010
    - Verify all features pass leakage test (IC_ratio < 1.20)
    - _Requirements: 17.6, 17.7, 50.1, 50.2, 50.3, 50.4_

  - [ ] 57.2 Generate final validation report
    - Document all success criteria met
    - Compare final IC to baseline IC (0.030)
    - Calculate total IC improvement percentage
    - Document all phases completed and gates passed
    - _Requirements: 50.5, 50.6, 50.7_

  - [ ] 57.3 Create comprehensive documentation
    - Document all features with PIT audit entries
    - Document all experiments with IC deltas
    - Document all configuration versions
    - Document all risk events and mitigations
    - _Requirements: 2.6, 12.5, 43.4, 18.6_

  - [ ]* 57.4 Write integration tests for complete system
    - Test end-to-end pipeline from data loading to prediction
    - Test all phases execute successfully
    - Test gate enforcement across all phases
    - _Requirements: 50.1, 50.2, 50.3_

- [ ] 58. Final checkpoint - Complete system validation
  - Verify all 7 phases completed successfully
  - Verify all gates passed
  - Verify final IC >= 0.047 and Sharpe > 0.25
  - Verify all regime IC > 0.010
  - Verify complete audit trail and documentation
  - Ensure all tests pass, ask the user if questions arise.


## Notes

### Implementation Approach

This implementation plan follows a strict phased approach with gate enforcement between phases. Each phase builds incrementally on the previous phase, with comprehensive validation at each checkpoint.

### Key Principles

1. **Single-Change Experiments**: Each experiment changes exactly one thing to isolate IC contribution
2. **PIT Compliance**: All features undergo rigorous PIT audit and automated leakage testing
3. **Feature Budget Discipline**: Strict enforcement of N/5 rule to prevent overfitting
4. **Gate Enforcement**: Hard stops between phases if performance targets not met
5. **Regime Robustness**: All regimes must achieve IC > 0.010 before proceeding

### Testing Strategy

- **Unit Tests**: Verify specific examples, edge cases, and error conditions
- **Property Tests**: Verify universal properties across all inputs (minimum 100 iterations)
- **Integration Tests**: Verify end-to-end pipeline functionality
- **Optional Tasks**: Tasks marked with `*` are optional testing tasks that can be skipped for faster MVP

### Conditional Features

Some features are conditional based on gate evaluation:
- **Dual-Horizon Architecture** (Phase 4): Implement only if Sharpe improvement >= 0.05
- **Trendlyne Consensus** (Phase 6): Implement only if API subscription available
- **Sequence Models** (Phase 7): Implement only if IC improvement >= 0.003

### Timeline Estimate

- Phase 0: 1 week (baseline stabilization)
- Phase 1: 2 weeks (6 features + sector dummies)
- Phase 2: 2 weeks (bulk deal integration)
- Phase 3: 2 weeks (regime overlay + hold-out validation)
- Phase 4: 1 week (earnings surprise + dual-horizon evaluation)
- Phase 5: 1 week (universe expansion)
- Phase 6: 1 week (advanced signals)
- Phase 7: 2 weeks (sequence models)
- **Total: 12 weeks**

### Success Metrics

- **Primary**: IC >= 0.047 (57% improvement from baseline 0.030)
- **Secondary**: Sharpe ratio > 0.25 after transaction costs
- **Regime**: All 4 regimes achieve IC > 0.010
- **Data Integrity**: All features pass leakage test (IC_ratio < 1.20)
- **Process**: Complete experiment audit trail and configuration versioning

### Risk Mitigation

The implementation includes automated detection and mitigation for 8 identified failure modes:
1. PIT leakage → Automated leakage testing
2. Feature correlation → Correlation matrix monitoring
3. Regime underperformance → Regime-conditional weights
4. Overfitting → Feature budget enforcement
5. IC degradation → Gate enforcement
6. Data staleness → Freshness validation
7. Train/test gap → Walk-forward validation
8. Survivorship bias → Delisting event handling
