# Implementation Plan: Probabilistic Forecasting Spine

## ⚠️ CRITICAL: READ THIS FIRST

**DO NOT START TASK 1 WITHOUT COMPLETING TASK 0**

This implementation plan contains 19 tasks for building institutional-grade forecasting infrastructure. However, **70% of this infrastructure is premature if your signals are weak**.

Before building any architecture, you MUST complete **Task 0: Signal Reality Audit**. This task validates whether your signals contain enough predictive power to justify the complexity of Tasks 1-19.

**The brutal truth**: A perfect forecasting spine on weak signals produces a perfectly engineered disappointment.

**Decision rule**:
- Mean IC < 0.015 → STOP, redesign signals
- Mean IC 0.015-0.025 → Build minimal ridge only (skip Bayesian, skip hierarchical)
- Mean IC > 0.025 & stable → Proceed with full spine

**If Task 0 fails validation, do NOT proceed to Task 1. Instead, pivot to:**
- Volatility/dispersion forecasting (often stronger than return forecasting)
- Regime timing instead of cross-sectional ranking
- Allocator research instead of signal research

## Overview

This implementation plan breaks down the probabilistic forecasting framework into discrete, incremental coding tasks. The approach follows a bottom-up strategy: build core components first (signals, features, models), then add monitoring layers, and finally integrate with existing Northstar components. Each task builds on previous work, with checkpoints to validate functionality before proceeding.

**Task 0 is the foundation. Everything else is conditional on Task 0 passing validation.**

## Tasks

- [ ] 0. Signal Reality Audit (MANDATORY - DO NOT SKIP)
  - **This task MUST be completed before any infrastructure is built**
  - **If this task fails validation, STOP implementation and redesign signals**
  - [ ] 0.1 Create minimal signal audit script
    - Load historical market data (2010-2024 or available range)
    - Implement top 5 candidate signals (momentum, valuation, quality, liquidity, macro)
    - Compute cross-sectional z-scores for each signal
    - Compute 10-day forward excess returns (relative to universe mean)
    - No models, no ridge regression, no architecture - just raw signal vs. outcome
    - _Purpose: Validate signal strength before building infrastructure_
  
  - [ ] 0.2 Compute rolling walk-forward IC
    - Use 3-year rolling window (or maximum available)
    - For each date t: compute IC = corr(signal_t, forward_return_t)
    - Store IC time series for each signal
    - Compute mean IC, std IC, % positive months
    - _Purpose: Measure predictive power without look-ahead bias_
  
  - [ ] 0.3 Compute regime-conditional IC
    - Split data by market regime (low-vol, high-vol, crisis)
    - Compute IC separately for each regime
    - Identify if IC flips sign across regimes
    - _Purpose: Validate if regime modeling is justified_
  
  - [ ] 0.4 Compute crisis-period IC
    - Define crisis periods: 2008-09-15 to 2009-03-09, 2020-02-20 to 2020-04-07
    - Compute IC during crisis periods only
    - Compare crisis IC to normal-period IC
    - _Purpose: Validate signal survival during extreme conditions_
  
  - [ ] 0.5 Compute IC decay curve
    - Compute IC at multiple horizons: 5-day, 10-day, 20-day, 60-day
    - Plot IC decay over time
    - Measure IC half-life
    - _Purpose: Validate forecast horizon alignment_
  
  - [ ] 0.6 Compute long-short decile portfolio Sharpe
    - Rank assets by signal into deciles
    - Long top decile, short bottom decile, equal weight
    - Compute portfolio returns and Sharpe ratio
    - No optimizer, no constraints - just raw signal ranking power
    - _Purpose: Validate economic significance of signal_
  
  - [ ] 0.7 Generate signal audit report
    - Summarize all metrics in structured report
    - Include visualizations: IC time series, IC by regime, decay curves
    - Flag signals that fail validation thresholds
    - _Purpose: Decision document for proceeding or stopping_
  
  - [ ] 0.8 DECISION CHECKPOINT - Apply validation rules
    - **STOP CONDITION 1**: If mean IC < 0.015 → STOP, redesign signals
    - **STOP CONDITION 2**: If stability ratio < 0.5 → STOP, signals too unstable
    - **STOP CONDITION 3**: If crisis IC flips sign → STOP, signals fail stress test
    - **PROCEED CONDITION 1**: If mean IC 0.015-0.025 → Build minimal ridge only (skip Bayesian)
    - **PROCEED CONDITION 2**: If mean IC > 0.025 & stable → Proceed with full spine
    - **PROCEED CONDITION 3**: If crisis IC flips sign but mean IC > 0.03 → Add regime modeling
    - **Document decision and rationale before proceeding to Task 1**

- [ ] 1. Set up project structure and core data models
  - Create directory structure: `src/forecasting/` with subdirectories for signals, features, models, monitoring, integration
  - Define core data models: `ForecastDistribution`, `ForecastOutput`, `SignalMatrix`, `FeatureMatrix`, `RegimeProbabilities`, `DecayAlert`
  - Implement serialization methods (to_dict, from_dict, to_json, from_json) for all data models
  - Set up configuration schema and YAML loading
  - Set up testing framework (pytest, hypothesis for property-based testing)
  - _Requirements: 21.1, 21.2, 24.1, 24.3_

- [ ]* 1.1 Write property test for data model serialization
  - **Property 18: JSON Serialization Round-Trip**
  - **Validates: Requirements 21.1**

- [ ] 2. Implement Signal Layer
  - [ ] 2.1 Create SignalLayer base class with compute_signals interface
    - Implement signal computation for Trend/Momentum bucket (momentum, RSI, volume-weighted momentum)
    - Implement signal computation for Valuation bucket (P/E, P/B, earnings yield, dividend yield)
    - Implement signal computation for Quality bucket (ROE, ROA, profit margin, debt-to-equity)
    - Implement signal computation for Liquidity/Microstructure bucket (bid-ask spread, volume, Amihud illiquidity)
    - Implement signal computation for Cross-Asset/Macro bucket (market correlation, beta, currency exposure)
    - _Requirements: 5.1, 5.4_
  
  - [ ] 2.2 Implement orthogonality enforcement within buckets
    - Compute pairwise correlations within each bucket
    - Apply Gram-Schmidt orthogonalization if correlation > 0.3
    - _Requirements: 5.2_
  
  - [ ] 2.3 Implement graceful error handling for missing data
    - Handle missing data for individual assets without breaking pipeline
    - Log warnings for missing data
    - _Requirements: 5.5_
  
  - [ ] 2.4 Write property tests for Signal Layer
    - **Property 5: Signal Bucket Structure**
    - **Property 6: Signal Orthogonality Within Buckets**
    - **Property 7: Temporal Correctness (No Look-Ahead)**
    - **Property 8: Graceful Error Handling**
    - **Validates: Requirements 5.1, 5.2, 5.4, 5.5**

- [ ] 3. Implement Feature Engine
  - [ ] 3.1 Create FeatureEngine class with contextualize_signals interface
    - Implement regime interaction feature construction (signal × regime_probability)
    - Implement cross-sectional normalization (demean and scale by std)
    - Validate time alignment (no look-ahead)
    - _Requirements: 6.1, 6.2, 6.4, 6.5_
  
  - [ ]* 3.2 Write property tests for Feature Engine
    - **Property 7: Temporal Correctness (No Look-Ahead)**
    - **Property 9: Feature Normalization**
    - **Validates: Requirements 6.4, 6.5**

- [ ] 4. Checkpoint - Validate signal and feature pipeline
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 5. Implement Core Forecast Models
  - [ ] 5.1 Implement Ridge Regression for cross-sectional returns
    - Implement fit method with L2 regularization: β = (X'X + λI)^(-1) X'y
    - Implement predict method with uncertainty quantification
    - Implement hyperparameter selection using walk-forward cross-validation
    - Apply cross-sectional normalization to predictions (demean)
    - _Requirements: 7.1, 7.2, 7.3, 7.4_
  
  - [ ]* 5.2 Write property tests for Ridge model
    - **Property 2: Cross-Sectional Normalization**
    - **Property 3: Distribution Output Completeness**
    - **Property 7: Temporal Correctness (No Look-Ahead)**
    - **Validates: Requirements 1.2, 7.3, 7.4, 12.4**
  
  - [ ] 5.3 Implement HAR model for volatility forecasting
    - Implement fit method with daily, weekly, monthly components
    - Implement regime-dependent coefficient adaptation
    - Implement predict method with uncertainty quantification
    - Validate non-overlapping windows for realized volatility computation
    - _Requirements: 8.1, 8.2, 8.3, 8.4_
  
  - [ ]* 5.4 Write property tests for HAR model
    - **Property 10: HAR Model Structure**
    - **Property 11: Non-Overlapping Validation Windows**
    - **Property 3: Distribution Output Completeness**
    - **Validates: Requirements 8.1, 8.3, 8.4**
  
  - [ ] 5.5 Implement Logistic model for tail probability
    - Implement fit method with class imbalance handling (weighted logistic regression)
    - Implement predict method outputting calibrated probabilities (not raw logits)
    - Apply regularization for rare tail events
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_
  
  - [ ]* 5.6 Write property tests for tail probability model
    - **Property 4: Valid Probability Outputs**
    - **Validates: Requirements 9.4**
  
  - [ ] 5.7 Implement Logistic model for regime transition probability
    - Implement fit method using regime features
    - Implement predict method outputting transition probability
    - _Requirements: 3.1, 3.2_
  
  - [ ]* 5.8 Write property tests for regime transition model
    - **Property 4: Valid Probability Outputs**
    - **Validates: Requirements 3.1**

- [ ] 6. Checkpoint - Validate all forecast models
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 7. Implement Calibration Monitor
  - [ ] 7.1 Create CalibrationMonitor class
    - Implement record_forecast and record_realized methods
    - Implement compute_ic method (Pearson correlation between forecast and realized)
    - Implement compute_calibration_metrics (directional accuracy, MAE, calibration slope/intercept)
    - Implement validate_performance_bounds (check DA: 52-57%, IC: 0.03-0.06, Sharpe: 1-1.8)
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 18.1, 18.2, 18.3, 18.4, 18.5_
  
  - [ ]* 7.2 Write property tests for Calibration Monitor
    - **Property 12: Forecast Recording**
    - **Property 13: IC Computation Correctness**
    - **Property 17: Performance Bounds Validation**
    - **Validates: Requirements 10.1, 10.3, 18.1, 18.2**

- [ ] 8. Implement Decay Monitor
  - [ ] 8.1 Create DecayMonitor class
    - Implement compute_stability_ratio (IC_recent / IC_historical)
    - Implement compute_regime_dependent_ic
    - Implement validate_crisis_survival (test IC during 2008, 2020 crises)
    - Implement detect_decay method (alert if stability_ratio < 0.7)
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 19.1, 19.2, 19.4_
  
  - [ ]* 8.2 Write property tests for Decay Monitor
    - **Property 14: Stability Ratio Computation**
    - **Validates: Requirements 11.1**

- [ ] 9. Implement ForecastEngine integration layer
  - [ ] 9.1 Create ForecastEngine class
    - Wire together SignalLayer, FeatureEngine, all forecast models, monitors
    - Implement generate_forecasts method (orchestrate full pipeline)
    - Implement graceful degradation (cached regime probs if Market_Brain unavailable)
    - Implement error isolation (continue processing other assets if one fails)
    - Implement conservative forecasts under high uncertainty (shrink toward zero)
    - _Requirements: 1.1, 2.1, 4.1, 23.1, 23.2, 23.4_
  
  - [ ] 9.2 Implement regime probability validation
    - Validate probabilities sum to 1 and all non-negative
    - _Requirements: 15.5_
  
  - [ ] 9.3 Implement covariance matrix computation
    - Compute forecast covariance matrix for portfolio optimization
    - Ensure matrix is symmetric and positive semi-definite
    - _Requirements: 16.4_
  
  - [ ]* 9.4 Write property tests for ForecastEngine
    - **Property 1: Forecast Completeness**
    - **Property 8: Graceful Error Handling**
    - **Property 15: Regime Probability Validation**
    - **Property 16: Covariance Matrix Properties**
    - **Property 19: Forecast Output Field Completeness**
    - **Property 21: Conservative Forecasts Under High Uncertainty**
    - **Validates: Requirements 1.1, 2.1, 4.1, 15.5, 16.4, 21.2, 23.2, 23.4**

- [ ] 10. Checkpoint - Validate end-to-end forecast generation
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 11. Implement integration with Northstar components
  - [ ] 11.1 Create MarketBrainClient
    - Implement get_regime_probabilities method with HTTP client
    - Implement caching with TTL
    - Implement timeout and retry logic
    - _Requirements: 15.1, 15.2, 15.3, 15.4_
  
  - [ ] 11.2 Create CapitalAllocatorClient
    - Implement update_forecasts method to send mean-variance parameters
    - Implement send tail probabilities for CVaR constraints
    - Implement signal to reduce position sizes when uncertainty is high
    - _Requirements: 16.1, 16.2, 16.3, 16.5_
  
  - [ ] 11.3 Create RiskAuthorityClient
    - Implement update_tail_risk method to send tail probabilities and volatility
    - Implement notification when tail probability exceeds threshold
    - Implement staleness check (prevent using stale tail probability data)
    - _Requirements: 17.1, 17.2, 17.4, 17.5_
  
  - [ ]* 11.4 Write integration tests
    - Test Market_Brain integration with mock server
    - Test Capital_Allocator integration with mock server
    - Test Risk_Authority integration with mock server
    - Test graceful degradation when services unavailable

- [ ] 12. Implement logging and audit trail
  - [ ] 12.1 Create comprehensive logging
    - Log all input features, model parameters, output forecasts on each generation
    - Log training data range, hyperparameters, validation metrics on model retraining
    - Log decay metrics and recommended actions when decay detected
    - Log override reason and tail probability when Risk_Authority overrides
    - Implement immutable timestamps for regulatory compliance
    - _Requirements: 22.1, 22.2, 22.3, 22.4, 22.5_
  
  - [ ]* 12.2 Write property test for logging
    - **Property 20: Comprehensive Logging**
    - **Validates: Requirements 22.1**

- [ ] 13. Implement configuration management
  - [ ] 13.1 Create configuration loading and validation
    - Implement YAML configuration loading at startup
    - Implement hot reload (reload configuration without restart)
    - Implement schema validation before applying configuration
    - Support environment-specific configurations (dev, staging, production)
    - Reject invalid configuration and log error without crashing
    - _Requirements: 24.1, 24.2, 24.3, 24.4, 24.5_
  
  - [ ]* 13.2 Write property test for configuration
    - **Property 22: Configuration Validation**
    - **Validates: Requirements 24.1, 24.3**

- [ ] 14. Implement performance optimizations
  - [ ] 14.1 Implement caching layer
    - Cache signal computations (invalidate on new data)
    - Cache feature matrices (invalidate on regime update)
    - Cache model predictions (invalidate on model update)
    - Implement LRU cache with size limits
    - _Requirements: 25.4_
  
  - [ ] 14.2 Implement parallel processing
    - Parallelize signal computation across assets using thread pool
    - Parallelize forecast generation across assets using thread pool
    - _Requirements: 25.1, 25.2_
  
  - [ ] 14.3 Implement latency monitoring
    - Track latency for full universe forecasts (budget: 5 seconds)
    - Track latency for single asset forecasts (budget: 100ms)
    - Track latency for model retraining (budget: 60 seconds)
    - Log performance warning and identify bottleneck when budget exceeded
    - _Requirements: 25.1, 25.2, 25.3, 25.5_
  
  - [ ]* 14.4 Write property test for caching
    - **Property 23: Cache Effectiveness**
    - **Validates: Requirements 25.4**

- [ ] 15. Implement walk-forward validation framework
  - [ ] 15.1 Create walk-forward validation harness
    - Implement rolling window validation (train on t-252:t, validate on t+1:t+10)
    - Implement hyperparameter selection without look-ahead bias
    - Compute out-of-sample IC, directional accuracy, Sharpe
    - Check for structural breaks when expanding training window
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 20.1, 20.2, 20.3, 20.4, 20.5_
  
  - [ ]* 15.2 Write unit tests for walk-forward validation
    - Test that training data timestamps < validation data timestamps
    - Test that hyperparameters are selected using only training data
    - Test that validation metrics use only out-of-sample forecasts

- [ ] 16. Implement crisis stress testing framework
  - [ ] 16.1 Create crisis stress testing harness
    - Define crisis periods (2008-09-15 to 2009-03-09, 2020-02-20 to 2020-04-07)
    - Compute crisis-conditional IC
    - Validate forecast uncertainty increases during crisis
    - Prevent production deployment if crisis stress tests fail
    - _Requirements: 19.1, 19.2, 19.3, 19.4, 19.5_
  
  - [ ]* 16.2 Write unit tests for crisis stress testing
    - Test IC computation during crisis periods
    - Test uncertainty increase detection during crisis

- [ ] 17. Implement Bayesian hierarchical extensions (optional)
  - [ ] 17.1 Create Bayesian ridge regression model
    - Implement hierarchical priors for cross-sectional parameters
    - Implement posterior distribution computation using variational inference
    - Propagate parameter uncertainty to forecast uncertainty
    - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5_
  
  - [ ]* 17.2 Write unit tests for Bayesian extensions
    - Test posterior distribution computation
    - Test uncertainty propagation

- [ ] 18. Create example scripts and documentation
  - [ ] 18.1 Create example usage scripts
    - Example: Generate forecasts for sample data
    - Example: Run walk-forward validation
    - Example: Run crisis stress testing
    - Example: Monitor forecast performance
  
  - [ ] 18.2 Create operator documentation
    - Document configuration options
    - Document monitoring and alerting
    - Document retraining procedures
    - Document integration with Northstar components

- [ ] 19. Final checkpoint - End-to-end validation
  - Run full walk-forward validation on historical data
  - Run crisis stress tests (2008, 2020)
  - Validate performance bounds (DA: 52-57%, IC: 0.03-0.06, Sharpe: 1-1.8)
  - Validate integration with Market_Brain, Capital_Allocator, Risk_Authority
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- **TASK 0 IS MANDATORY**: Do not skip Task 0. It validates whether Tasks 1-19 are rational to build.
- **Task 0 decision checkpoint**: If signals fail validation, stop implementation and redesign signals.
- Tasks marked with `*` are optional and can be skipped for faster MVP (but only if Task 0 passes)
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties (minimum 100 iterations each)
- Unit tests validate specific examples and edge cases
- Integration tests validate interaction with external components
- Walk-forward validation and crisis stress testing are critical for production readiness
- Bayesian extensions (task 17) are optional enhancements for parameter uncertainty quantification
- **If Task 0 reveals mean IC < 0.02, consider pivoting to volatility forecasting instead of return forecasting**
- **Engineering complexity should scale with signal strength, not with architectural ambition**
