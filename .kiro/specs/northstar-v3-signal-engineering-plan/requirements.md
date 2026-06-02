# Requirements Document

## Introduction

This document specifies requirements for the Northstar V3 Signal Engineering Forward Plan, a systematic quantitative equity research improvement initiative for Indian NSE/BSE markets. The plan targets Information Coefficient (IC) improvement from current baseline 0.030 to gate target 0.040 and stretch target 0.050+ through 7 phased implementations over 12 weeks. The system addresses critical problems identified in adversarial review including point-in-time (PIT) data leakage, over-regularization, feature correlation management, and regime-specific performance gaps.

## Glossary

- **Signal_Engineering_System**: The complete quantitative research pipeline including feature engineering, model training, validation, and deployment
- **IC** (Information Coefficient): Spearman rank correlation between predicted returns and actual forward returns, primary performance metric
- **PIT** (Point-In-Time): Data integrity constraint ensuring no future information leaks into historical analysis
- **Feature_Budget**: Maximum number of features allowed based on sample size to prevent overfitting (N/5 rule)
- **Regime**: Market state classification based on volatility and trend conditions
- **XGBoost_Model**: Gradient boosting machine learning model used for return prediction
- **Bulk_Deal**: Large block trades reported to NSE/BSE, potential signal of informed trading
- **SUE** (Standardized Unexpected Earnings): Earnings surprise metric normalized by historical volatility
- **ADT*
* (Average Daily Turnover): Daily trading volume in rupees, used for liquidity filtering
- **Leakage_Test**: Automated validation that compares IC with and without time-shifted data
- **SHAP** (SHapley Additive exPlanations): Model interpretation method for validating feature importance
- **Winsorization**: Statistical technique to limit extreme values to reduce outlier impact
- **Free_Float**: Percentage of shares available for public trading, excluding promoter holdings
- **Promoter_Pledge**: Percentage of promoter shares pledged as collateral, potential distress signal
- **Amihud_Illiquidity**: Price impact measure calculated as absolute return divided by rupee volume
- **BAB_Beta**: Betting-Against-Beta factor, low-beta stocks outperformance measure
- **Piotroski_F_Score**: 9-point fundamental strength score based on profitability, leverage, and efficiency
- **MAX_Lottery**: Maximum daily return over past month, lottery-like stock preference measure
- **Earnings_Quality_Score**: Composite metric assessing accruals quality and cash flow alignment
- **Trendlyne_Consensus**: Aggregated analyst earnings estimates and revisions
- **TCN** (Temporal Convolutional Network): Deep learning architecture for sequence modeling
- **Universe**: Set of stocks eligible for analysis and trading
- **Gate**: Minimum performance threshold required to proceed to next phase
- **Experiment**: Single controlled change to the system with before/after validation

## Requirements

### Requirement 1: Phase 0 - Baseline Stabilization

**User Story:** As a quantitative researcher, I want to stabilize the baseline model performance, so that subsequent improvements build on a reliable foundation.

#### Acceptance Criteria

1. THE Signal_Engineering_System SHALL revert XGBoost_Model max_depth to 4 and min_child_weight to 20
2. THE Signal_Engineering_System SHALL correct the accruals calculation sign inversion
3. THE Signal_Engineering_System SHALL fix the PIT bug in regime_engine.py date alignment
4. WHEN the baseline model is trained, THE Signal_Engineering_System SHALL achieve IC greater than or equal to 0.032
5. THE Leakage_Test SHALL execute for all existing features and produce IC_ratio less than 1.20
6. FOR ALL existing features, parsing financial data then applying PIT constraints then re-parsing SHALL produce equivalent timestamps (round-trip property)

### Requirement 2: PIT Audit Protocol

**User Story:** As a quantitative researcher, I want rigorous point-in-time data integrity validation, so that no future information contaminates historical analysis.

#### Acceptance Criteria

1. WHEN a new feature is added, THE Signal_Engineering_System SHALL document the data timestamp source
2. WHEN a new feature is added, THE Signal_Engineering_System SHALL document the public availability date with regulatory reference
3. WHEN a new feature is added, THE Signal_Engineering_System SHALL apply a safety buffer of at least 1 trading day
4. WHEN a new feature is added, THE Leakage_Test SHALL execute and produce IC_ratio less than 1.20
5. IF the Leakage_Test produces IC_ratio greater than or equal to 1.20, THEN THE Signal_Engineering_System SHALL reject the feature
6. THE Signal_Engineering_System SHALL maintain a PIT audit log for all features with timestamp documentation
7. WHEN quarterly financial data is used, THE Signal_Engineering_System SHALL apply a 2-day buffer after NSE announcement date

### Requirement 3: Feature Budget Enforcement

**User Story:** As a quantitative researcher, I want to enforce feature count limits based on sample size, so that the model does not overfit.

#### Acceptance Criteria

1. WHILE the Universe contains 150 stocks, THE Signal_Engineering_System SHALL limit features to a maximum of 32
2. WHILE the Universe contains 300 stocks, THE Signal_Engineering_System SHALL limit features to a maximum of 45
3. WHEN feature count exceeds Feature_Budget, THE Signal_Engineering_System SHALL reject new feature additions
4. THE Signal_Engineering_System SHALL calculate Feature_Budget as sample_size divided by 5
5. THE Signal_Engineering_System SHALL log Feature_Budget utilization percentage after each feature addition

### Requirement 4: Phase 1 - Controlled Feature Additions

**User Story:** As a quantitative researcher, I want to add proven anomaly factors sequentially, so that I can measure incremental IC contribution.

#### Acceptance Criteria

1. THE Signal_Engineering_System SHALL add BAB_Beta feature with winsorization at 1st and 99th percentiles
2. THE Signal_Engineering_System SHALL add Amihud_Illiquidity feature with log transformation
3. THE Signal_Engineering_System SHALL add Piotroski_F_Score feature with 9-point calculation
4. THE Signal_Engineering_System SHALL add 3-month momentum feature with 1-month lag
5. THE Signal_Engineering_System SHALL add MAX_Lottery feature as maximum daily return over 21 days
6. THE Signal_Engineering_System SHALL add Earnings_Quality_Score feature combining accruals and cash flow metrics
7. WHEN each feature is added, THE Signal_Engineering_System SHALL execute one Experiment with before/after IC measurement
8. WHEN Phase 1 is complete, THE Signal_Engineering_System SHALL achieve IC greater than or equal to 0.037
9. THE Signal_Engineering_System SHALL add sector dummy variables for 11 GICS sectors
10. IF any feature has pairwise correlation greater than 0.70 with existing features, THEN THE Signal_Engineering_System SHALL log a correlation warning

### Requirement 5: Signal Correlation Management

**User Story:** As a quantitative researcher, I want to manage feature correlations, so that I avoid redundant signals and inflated IC projections.

#### Acceptance Criteria

1. WHEN projecting IC contribution for a new feature, THE Signal_Engineering_System SHALL cap the projection at 0.003
2. WHEN a new feature is added, THE Signal_Engineering_System SHALL calculate pairwise correlations with all existing features
3. WHEN a new feature is added, THE Signal_Engineering_System SHALL execute SHAP analysis to validate feature importance
4. IF SHAP importance for a feature is less than 0.01, THEN THE Signal_Engineering_System SHALL flag the feature for removal consideration
5. THE Signal_Engineering_System SHALL maintain a correlation matrix for all active features
6. WHEN feature correlation exceeds 0.85, THE Signal_Engineering_System SHALL reject the redundant feature

### Requirement 6: Phase 2 - Bulk Deal Signal Integration

**User Story:** As a quantitative researcher, I want to extract signals from bulk deal transactions, so that I can capture informed trading activity.

#### Acceptance Criteria

1. THE Signal_Engineering_System SHALL classify bulk deal buyers using fuzzy string matching with 85% similarity threshold
2. THE Signal_Engineering_System SHALL normalize bulk deal quantities by free float percentage
3. THE Signal_Engineering_System SHALL create 4 bulk deal features: net institutional buying, promoter buying, FII net flow, and DII net flow
4. WHEN bulk deal data is processed, THE Signal_Engineering_System SHALL apply survivorship bias filter excluding delisted stocks
5. WHEN bulk deal features are added, THE Leakage_Test SHALL verify PIT compliance with IC_ratio less than 1.20
6. WHEN Phase 2 is complete, THE Signal_Engineering_System SHALL achieve IC greater than or equal to 0.039
7. THE Signal_Engineering_System SHALL aggregate bulk deals over 21-day rolling windows

### Requirement 7: Phase 3 - Regime Overlay Implementation

**User Story:** As a quantitative researcher, I want to implement regime-conditional scoring, so that signals adapt to different market conditions.

#### Acceptance Criteria

1. THE Signal_Engineering_System SHALL implement a 2-axis regime framework using India_VIX and Nifty_200d_SMA
2. THE Signal_Engineering_System SHALL classify regimes into 4 states: risk_on_calm, risk_on_volatile, risk_off_calm, risk_off_volatile
3. WHEN India_VIX is greater than 20, THE Signal_Engineering_System SHALL classify the regime as volatile
4. WHEN Nifty_50 price is above Nifty_200d_SMA, THE Signal_Engineering_System SHALL classify the regime as risk_on
5. THE Signal_Engineering_System SHALL apply regime-conditional feature weights in XGBoost_Model
6. WHEN Phase 3 is complete, THE Signal_Engineering_System SHALL achieve IC greater than or equal to 0.012 in risk_on_volatile regime
7. THE Signal_Engineering_System SHALL replace the 14-label regime system with the 4-regime system
8. FOR ALL regimes, THE Signal_Engineering_System SHALL achieve IC greater than 0.010

### Requirement 7A: Regime Weight Hold-Out Validation

**User Story:** As a quantitative researcher, I want to validate regime weights on hold-out data, so that I can protect against regime overfitting before deployment.

#### Acceptance Criteria

1. THE Signal_Engineering_System SHALL reserve 2013-2016 period as hold-out validation data for regime weights
2. THE Signal_Engineering_System SHALL train regime-conditional weights using data after 2016 only
3. WHEN regime weights are finalized, THE Signal_Engineering_System SHALL validate performance on 2013-2016 hold-out period
4. IF hold-out period IC degrades by more than 0.010 compared to training period IC, THEN THE Signal_Engineering_System SHALL flag regime overfitting risk
5. THE Signal_Engineering_System SHALL document hold-out validation results before deployment
6. THE Signal_Engineering_System SHALL compare hold-out IC to baseline IC for each regime separately

### Requirement 8: Phase 4 - Earnings Surprise Signal

**User Story:** As a quantitative researcher, I want to incorporate earnings surprise signals, so that I can capture post-earnings announcement drift.

#### Acceptance Criteria

1. THE Signal_Engineering_System SHALL scrape NSE earnings announcement dates from NSE corporate announcements page
2. THE Signal_Engineering_System SHALL calculate SUE using seasonal random-walk expectation model
3. THE Signal_Engineering_System SHALL normalize earnings surprise by 8-quarter rolling standard deviation
4. WHEN earnings announcement data is processed, THE Leakage_Test SHALL verify PIT compliance with IC_ratio less than 1.20
5. THE Signal_Engineering_System SHALL evaluate dual-horizon architecture with 5-day and 21-day forward returns
6. WHEN Phase 4 is complete, THE Signal_Engineering_System SHALL achieve IC greater than or equal to 0.041
7. THE Signal_Engineering_System SHALL apply a 1-day buffer after NSE announcement timestamp
8. WHERE dual-horizon architecture is implemented, THE Signal_Engineering_System SHALL train separate models for each horizon

### Requirement 8A: Dual-Horizon Decision Gate

**User Story:** As a quantitative researcher, I want a clear go/no-go criterion for dual-horizon implementation, so that I avoid unnecessary complexity without sufficient benefit.

#### Acceptance Criteria

1. WHEN evaluating dual-horizon architecture, THE Signal_Engineering_System SHALL calculate Sharpe ratio improvement over single-horizon baseline
2. IF dual-horizon Sharpe improvement is greater than or equal to 0.05, THEN THE Signal_Engineering_System SHALL implement dual-horizon architecture
3. IF dual-horizon Sharpe improvement is less than 0.05, THEN THE Signal_Engineering_System SHALL retain single 5-day model only
4. THE Signal_Engineering_System SHALL document the decision rationale with Sharpe comparison metrics
5. THE Signal_Engineering_System SHALL evaluate complexity cost including training time and maintenance overhead

### Requirement 9: Phase 5 - Universe Expansion

**User Story:** As a quantitative researcher, I want to expand the stock universe from 150 to 300 stocks, so that I can increase strategy capacity and diversification.

#### Acceptance Criteria

1. THE Signal_Engineering_System SHALL expand Universe from 150 stocks to 300 stocks
2. THE Signal_Engineering_System SHALL build a point-in-time universe membership table tracking index additions and deletions
3. WHEN filtering stocks for Universe, THE Signal_Engineering_System SHALL apply minimum ADT threshold of Rs 2 crore
4. WHEN Universe is expanded, THE Signal_Engineering_System SHALL increase Feature_Budget to 45 features maximum
5. WHEN Phase 5 is complete, THE Signal_Engineering_System SHALL achieve IC greater than or equal to 0.043
6. THE Signal_Engineering_System SHALL exclude stocks with less than 252 trading days of history
7. THE Signal_Engineering_System SHALL rebalance Universe membership quarterly based on liquidity criteria

### Requirement 10: Phase 6 - Advanced Signal Integration

**User Story:** As a quantitative researcher, I want to add advanced alternative data signals, so that I can capture unique information sources.

#### Acceptance Criteria

1. THE Signal_Engineering_System SHALL integrate Trendlyne_Consensus earnings estimate revisions
2. THE Signal_Engineering_System SHALL calculate consensus revision diffusion as percentage of analysts raising estimates
3. THE Signal_Engineering_System SHALL add promoter pledge change signal as quarterly delta in pledge percentage
4. THE Signal_Engineering_System SHALL add MAX5 lottery feature as maximum daily return over 5 days
5. WHEN Trendlyne_Consensus data is processed, THE Leakage_Test SHALL verify PIT compliance with IC_ratio less than 1.20
6. WHEN Phase 6 is complete, THE Signal_Engineering_System SHALL achieve IC greater than or equal to 0.045
7. THE Signal_Engineering_System SHALL apply winsorization to promoter pledge changes at 5th and 95th percentiles

### Requirement 11: Phase 7 - Sequence Model Ensemble

**User Story:** As a quantitative researcher, I want to evaluate deep learning sequence models, so that I can capture temporal dependencies beyond XGBoost capabilities.

#### Acceptance Criteria

1. WHERE sequence model implementation is pursued, THE Signal_Engineering_System SHALL implement TCN architecture with dilated convolutions
2. WHERE sequence model implementation is pursued, THE Signal_Engineering_System SHALL implement Transformer architecture with positional encoding
3. WHERE sequence model implementation is pursued, THE Signal_Engineering_System SHALL ensemble sequence model predictions with XGBoost_Model predictions
4. IF sequence model IC improvement is greater than or equal to 0.003, THEN THE Signal_Engineering_System SHALL deploy the ensemble model
5. IF sequence model IC improvement is less than 0.003, THEN THE Signal_Engineering_System SHALL retain XGBoost_Model only
6. WHERE ensemble is deployed, THE Signal_Engineering_System SHALL achieve IC greater than or equal to 0.047
7. WHERE sequence models are trained, THE Signal_Engineering_System SHALL use 60-day lookback windows
8. WHERE ensemble is deployed, THE Signal_Engineering_System SHALL weight XGBoost_Model at 60% and sequence model at 40%

### Requirement 12: Experiment Discipline Protocol

**User Story:** As a quantitative researcher, I want to enforce rigorous experiment discipline, so that I can isolate the impact of each change.

#### Acceptance Criteria

1. THE Signal_Engineering_System SHALL execute exactly one change per Experiment
2. WHEN an Experiment is executed, THE Signal_Engineering_System SHALL record baseline IC before the change
3. WHEN an Experiment is executed, THE Signal_Engineering_System SHALL record post-change IC after the change
4. WHEN an Experiment is executed, THE Signal_Engineering_System SHALL calculate IC delta as post-change IC minus baseline IC
5. THE Signal_Engineering_System SHALL maintain an experiment log with timestamps, changes, and IC deltas
6. IF an Experiment produces negative IC delta, THEN THE Signal_Engineering_System SHALL revert the change
7. THE Signal_Engineering_System SHALL use identical train/test splits across experiments for fair comparison

### Requirement 13: Gate Enforcement Protocol

**User Story:** As a quantitative researcher, I want to enforce hard gates between phases, so that I do not proceed with underperforming configurations.

#### Acceptance Criteria

1. WHEN a phase is complete, THE Signal_Engineering_System SHALL evaluate IC against the phase gate threshold
2. IF phase IC is less than gate threshold, THEN THE Signal_Engineering_System SHALL halt progression to next phase
3. IF phase IC is less than gate threshold, THEN THE Signal_Engineering_System SHALL require diagnostic analysis before retry
4. THE Signal_Engineering_System SHALL log gate evaluation results with pass/fail status
5. THE Signal_Engineering_System SHALL prevent feature additions when gate criteria are not met
6. WHEN a gate is failed, THE Signal_Engineering_System SHALL generate a diagnostic report identifying underperforming features

### Requirement 14: Leakage Test Framework

**User Story:** As a quantitative researcher, I want automated leakage detection tests, so that I can identify point-in-time violations systematically.

#### Acceptance Criteria

1. THE Leakage_Test SHALL calculate baseline IC using correct point-in-time data alignment
2. THE Leakage_Test SHALL calculate shifted IC using data shifted forward by 5 trading days
3. THE Leakage_Test SHALL calculate IC_ratio as shifted IC divided by baseline IC
4. WHEN IC_ratio is greater than or equal to 1.20, THE Leakage_Test SHALL flag the feature as leaking
5. THE Leakage_Test SHALL execute on all features in the feature set
6. THE Leakage_Test SHALL generate a leakage report with IC_ratio for each feature
7. THE Leakage_Test SHALL use out-of-sample test period for validation
8. WHEN a feature is flagged as leaking, THE Signal_Engineering_System SHALL remove the feature from the model

### Requirement 15: Feature Engineering Transformations

**User Story:** As a quantitative researcher, I want to apply standard feature engineering transformations, so that features have appropriate distributions for modeling.

#### Acceptance Criteria

1. WHEN a feature has extreme outliers, THE Signal_Engineering_System SHALL apply winsorization at 1st and 99th percentiles
2. WHEN a feature has right-skewed distribution, THE Signal_Engineering_System SHALL apply log transformation
3. WHEN a feature requires temporal lag, THE Signal_Engineering_System SHALL apply 1-month lag to avoid short-term reversal
4. THE Signal_Engineering_System SHALL create sector dummy variables using one-hot encoding
5. THE Signal_Engineering_System SHALL standardize features to zero mean and unit variance within each training fold
6. WHEN missing values are present, THE Signal_Engineering_System SHALL apply forward-fill followed by median imputation
7. THE Signal_Engineering_System SHALL rank-transform features within each cross-section to reduce outlier impact

### Requirement 16: Data Source Integration

**User Story:** As a quantitative researcher, I want to integrate required data sources, so that all features have reliable data feeds.

#### Acceptance Criteria

1. THE Signal_Engineering_System SHALL integrate NSE earnings announcement dates from NSE corporate announcements API
2. THE Signal_Engineering_System SHALL integrate India_VIX daily history from NSE indices API
3. THE Signal_Engineering_System SHALL integrate NSE historical index compositions from NSE historical data
4. THE Signal_Engineering_System SHALL integrate Screener quarterly financials from existing data pipeline
5. THE Signal_Engineering_System SHALL integrate bulk deals dataset with 333,826 historical records
6. WHERE Trendlyne_Consensus is implemented, THE Signal_Engineering_System SHALL integrate Trendlyne API with subscription credentials
7. THE Signal_Engineering_System SHALL validate data freshness with maximum staleness of 2 trading days
8. WHEN data source integration fails, THE Signal_Engineering_System SHALL log the failure and use cached data

### Requirement 17: Performance Validation and Reporting

**User Story:** As a quantitative researcher, I want comprehensive performance validation, so that I can assess model quality across multiple dimensions.

#### Acceptance Criteria

1. THE Signal_Engineering_System SHALL calculate IC as Spearman rank correlation between predictions and forward returns
2. THE Signal_Engineering_System SHALL calculate Sharpe ratio assuming 25 basis points transaction costs
3. THE Signal_Engineering_System SHALL report IC separately for each of the 4 regime states
4. THE Signal_Engineering_System SHALL calculate IC by sector to identify sector-specific performance
5. THE Signal_Engineering_System SHALL generate monthly IC time series to assess stability
6. WHEN final validation is complete, THE Signal_Engineering_System SHALL achieve IC greater than or equal to 0.047
7. WHEN final validation is complete, THE Signal_Engineering_System SHALL achieve Sharpe ratio greater than 0.25
8. THE Signal_Engineering_System SHALL use walk-forward validation with 24-month training windows and 3-month test windows
9. THE Signal_Engineering_System SHALL report turnover as percentage of portfolio changed per rebalance

### Requirement 18: Risk Register and Failure Mode Mitigation

**User Story:** As a quantitative researcher, I want to track and mitigate identified failure modes, so that I can proactively address risks.

#### Acceptance Criteria

1. THE Signal_Engineering_System SHALL maintain a risk register tracking 8 identified failure modes
2. WHEN PIT leakage is detected, THE Signal_Engineering_System SHALL execute the leakage mitigation protocol
3. WHEN feature correlation exceeds 0.85, THE Signal_Engineering_System SHALL execute the correlation mitigation protocol
4. WHEN any regime IC falls below 0.010, THE Signal_Engineering_System SHALL execute the regime performance mitigation protocol
5. WHEN Feature_Budget is exceeded, THE Signal_Engineering_System SHALL execute the overfitting mitigation protocol
6. THE Signal_Engineering_System SHALL log all risk events with timestamps and mitigation actions
7. THE Signal_Engineering_System SHALL generate weekly risk reports summarizing active risks and mitigations
8. IF IC degrades by more than 0.005 from previous phase, THEN THE Signal_Engineering_System SHALL trigger diagnostic analysis

### Requirement 19: Model Training and Hyperparameter Configuration

**User Story:** As a quantitative researcher, I want to configure XGBoost hyperparameters appropriately, so that the model balances bias and variance.

#### Acceptance Criteria

1. THE XGBoost_Model SHALL use max_depth of 4 to limit tree complexity
2. THE XGBoost_Model SHALL use min_child_weight of 20 to prevent overfitting on small samples
3. THE XGBoost_Model SHALL use learning_rate of 0.05 for stable convergence
4. THE XGBoost_Model SHALL use n_estimators of 200 for sufficient model capacity
5. THE XGBoost_Model SHALL use subsample of 0.8 for stochastic training
6. THE XGBoost_Model SHALL use colsample_bytree of 0.8 for feature sampling
7. THE XGBoost_Model SHALL use objective function 'reg:squarederror' for return prediction
8. WHEN training XGBoost_Model, THE Signal_Engineering_System SHALL use 5-fold time-series cross-validation
9. THE Signal_Engineering_System SHALL monitor validation loss to detect overfitting

### Requirement 20: Bulk Deal Buyer Classification

**User Story:** As a quantitative researcher, I want to classify bulk deal buyers accurately, so that I can distinguish informed from uninformed trading.

#### Acceptance Criteria

1. THE Signal_Engineering_System SHALL classify bulk deal buyers into 6 categories: FII, DII, Promoter, Institutional, Retail, Unknown
2. THE Signal_Engineering_System SHALL use fuzzy string matching with Levenshtein distance for buyer name matching
3. WHEN fuzzy matching similarity is greater than or equal to 85%, THE Signal_Engineering_System SHALL assign the buyer to the matched category
4. WHEN fuzzy matching similarity is less than 85%, THE Signal_Engineering_System SHALL assign the buyer to Unknown category
5. THE Signal_Engineering_System SHALL maintain a buyer classification lookup table with manual overrides
6. THE Signal_Engineering_System SHALL normalize bulk deal quantities by dividing by free float shares
7. THE Signal_Engineering_System SHALL aggregate bulk deals by category over 21-day rolling windows

### Requirement 21: Earnings Quality Score Calculation

**User Story:** As a quantitative researcher, I want to calculate earnings quality scores, so that I can identify companies with sustainable earnings.

#### Acceptance Criteria

1. THE Signal_Engineering_System SHALL calculate accruals as net income minus operating cash flow divided by total assets
2. THE Signal_Engineering_System SHALL calculate cash flow to income ratio as operating cash flow divided by net income
3. THE Signal_Engineering_System SHALL calculate accruals volatility as 8-quarter rolling standard deviation of accruals
4. THE Earnings_Quality_Score SHALL combine accruals, cash flow ratio, and accruals volatility with equal weights
5. THE Signal_Engineering_System SHALL winsorize Earnings_Quality_Score at 5th and 95th percentiles
6. THE Signal_Engineering_System SHALL apply PIT constraints using quarterly financial statement dates plus 2-day buffer

### Requirement 22: Piotroski F-Score Implementation

**User Story:** As a quantitative researcher, I want to calculate Piotroski F-Scores, so that I can identify fundamentally strong value stocks.

#### Acceptance Criteria

1. THE Signal_Engineering_System SHALL calculate 9 binary signals for Piotroski_F_Score: positive ROA, positive operating cash flow, ROA increase, accruals quality, gross margin increase, asset turnover increase, leverage decrease, liquidity increase, no equity issuance
2. THE Piotroski_F_Score SHALL sum the 9 binary signals to produce a score from 0 to 9
3. WHEN ROA is greater than 0, THE Signal_Engineering_System SHALL assign 1 point
4. WHEN operating cash flow is greater than 0, THE Signal_Engineering_System SHALL assign 1 point
5. WHEN current year ROA is greater than prior year ROA, THE Signal_Engineering_System SHALL assign 1 point
6. WHEN operating cash flow is greater than net income, THE Signal_Engineering_System SHALL assign 1 point
7. THE Signal_Engineering_System SHALL apply PIT constraints using annual financial statement dates plus 2-day buffer

### Requirement 23: Amihud Illiquidity Calculation

**User Story:** As a quantitative researcher, I want to calculate Amihud illiquidity measures, so that I can capture price impact and liquidity risk.

#### Acceptance Criteria

1. THE Signal_Engineering_System SHALL calculate daily Amihud_Illiquidity as absolute return divided by rupee volume
2. THE Signal_Engineering_System SHALL aggregate Amihud_Illiquidity over 21-day rolling windows using median
3. THE Signal_Engineering_System SHALL apply log transformation to Amihud_Illiquidity to reduce skewness
4. WHEN rupee volume is zero, THE Signal_Engineering_System SHALL exclude the observation from Amihud_Illiquidity calculation
5. THE Signal_Engineering_System SHALL winsorize Amihud_Illiquidity at 1st and 99th percentiles

### Requirement 24: BAB Beta Factor Implementation

**User Story:** As a quantitative researcher, I want to calculate betting-against-beta factors, so that I can capture the low-volatility anomaly.

#### Acceptance Criteria

1. THE Signal_Engineering_System SHALL calculate BAB_Beta as 252-day rolling regression beta against Nifty 50 index
2. THE Signal_Engineering_System SHALL use daily returns for beta estimation
3. THE Signal_Engineering_System SHALL require minimum 126 observations for beta calculation
4. THE Signal_Engineering_System SHALL winsorize BAB_Beta at 5th and 95th percentiles
5. THE Signal_Engineering_System SHALL apply 1-month lag to BAB_Beta to avoid short-term reversal

### Requirement 25: Momentum Feature Engineering

**User Story:** As a quantitative researcher, I want to calculate momentum features with appropriate lags, so that I can capture trend persistence while avoiding reversal.

#### Acceptance Criteria

1. THE Signal_Engineering_System SHALL calculate 3-month momentum as cumulative return from t-4 months to t-1 month
2. THE Signal_Engineering_System SHALL skip the most recent month to avoid short-term reversal
3. THE Signal_Engineering_System SHALL winsorize momentum at 1st and 99th percentiles
4. THE Signal_Engineering_System SHALL calculate momentum using log returns for compounding accuracy

### Requirement 26: MAX Lottery Feature Implementation

**User Story:** As a quantitative researcher, I want to calculate MAX lottery features, so that I can capture investor preference for lottery-like stocks.

#### Acceptance Criteria

1. THE Signal_Engineering_System SHALL calculate MAX_Lottery as maximum daily return over the past 21 trading days
2. THE Signal_Engineering_System SHALL calculate MAX5 as maximum daily return over the past 5 trading days
3. THE Signal_Engineering_System SHALL use simple returns for MAX calculation
4. THE Signal_Engineering_System SHALL winsorize MAX features at 99th percentile to limit extreme values

### Requirement 27: Standardized Unexpected Earnings (SUE) Calculation

**User Story:** As a quantitative researcher, I want to calculate standardized unexpected earnings, so that I can capture earnings surprise momentum.

#### Acceptance Criteria

1. THE Signal_Engineering_System SHALL calculate earnings surprise as actual EPS minus expected EPS
2. THE Signal_Engineering_System SHALL use seasonal random-walk model for expected EPS (EPS from 4 quarters ago)
3. THE Signal_Engineering_System SHALL normalize earnings surprise by 8-quarter rolling standard deviation
4. THE SUE SHALL be calculated as earnings surprise divided by standard deviation
5. THE Signal_Engineering_System SHALL winsorize SUE at 5th and 95th percentiles
6. WHEN earnings announcement date is available, THE Signal_Engineering_System SHALL apply 1-day buffer after announcement
7. WHEN earnings announcement date is not available, THE Signal_Engineering_System SHALL use financial statement date plus 30 days

### Requirement 28: Regime Classification Logic

**User Story:** As a quantitative researcher, I want to classify market regimes systematically, so that I can apply regime-conditional strategies.

#### Acceptance Criteria

1. WHEN India_VIX is less than or equal to 20 AND Nifty_50 is above Nifty_200d_SMA, THE Signal_Engineering_System SHALL classify regime as risk_on_calm
2. WHEN India_VIX is greater than 20 AND Nifty_50 is above Nifty_200d_SMA, THE Signal_Engineering_System SHALL classify regime as risk_on_volatile
3. WHEN India_VIX is less than or equal to 20 AND Nifty_50 is below Nifty_200d_SMA, THE Signal_Engineering_System SHALL classify regime as risk_off_calm
4. WHEN India_VIX is greater than 20 AND Nifty_50 is below Nifty_200d_SMA, THE Signal_Engineering_System SHALL classify regime as risk_off_volatile
5. THE Signal_Engineering_System SHALL calculate Nifty_200d_SMA using 200 trading days of Nifty 50 closing prices
6. THE Signal_Engineering_System SHALL update regime classification daily
7. THE Signal_Engineering_System SHALL log regime transitions with timestamps

### Requirement 29: Trendlyne Consensus Integration

**User Story:** As a quantitative researcher, I want to integrate Trendlyne consensus data, so that I can capture analyst revision signals.

#### Acceptance Criteria

1. WHERE Trendlyne_Consensus is implemented, THE Signal_Engineering_System SHALL integrate Trendlyne API for earnings estimates
2. WHERE Trendlyne_Consensus is implemented, THE Signal_Engineering_System SHALL calculate consensus revision diffusion as percentage of analysts raising estimates over past 30 days
3. WHERE Trendlyne_Consensus is implemented, THE Signal_Engineering_System SHALL apply PIT constraints using estimate revision dates
4. WHERE Trendlyne_Consensus is implemented, THE Signal_Engineering_System SHALL winsorize consensus revision diffusion at 5th and 95th percentiles

### Requirement 30: Promoter Pledge Signal Implementation

**User Story:** As a quantitative researcher, I want to track promoter pledge changes, so that I can identify potential financial distress signals.

#### Acceptance Criteria

1. THE Signal_Engineering_System SHALL calculate promoter pledge change as quarterly delta in pledge percentage
2. THE Signal_Engineering_System SHALL source promoter pledge data from Screener quarterly shareholding data
3. THE Signal_Engineering_System SHALL apply PIT constraints using shareholding pattern date plus 2-day buffer
4. THE Signal_Engineering_System SHALL winsorize promoter pledge change at 5th and 95th percentiles
5. WHEN promoter pledge data is missing, THE Signal_Engineering_System SHALL impute with zero change

### Requirement 31: Universe Liquidity Filtering

**User Story:** As a quantitative researcher, I want to filter stocks by liquidity, so that the universe contains only tradeable stocks.

#### Acceptance Criteria

1. THE Signal_Engineering_System SHALL calculate ADT as 21-day average of daily rupee volume
2. WHEN ADT is less than Rs 2 crore, THE Signal_Engineering_System SHALL exclude the stock from Universe
3. THE Signal_Engineering_System SHALL recalculate liquidity filters quarterly
4. THE Signal_Engineering_System SHALL maintain point-in-time universe membership records
5. THE Signal_Engineering_System SHALL exclude stocks with less than 252 trading days of price history

### Requirement 32: Survivorship Bias Mitigation

**User Story:** As a quantitative researcher, I want to mitigate survivorship bias, so that backtest results reflect realistic performance.

#### Acceptance Criteria

1. THE Signal_Engineering_System SHALL include delisted stocks in historical analysis up to delisting date
2. WHEN a stock is delisted due to forced delisting (fraud, suspension, insolvency), THE Signal_Engineering_System SHALL apply -100% return on delisting date
3. WHEN a stock is delisted due to voluntary delisting (merger, buyout, going private), THE Signal_Engineering_System SHALL use actual last traded price or buyout premium
4. THE Signal_Engineering_System SHALL maintain a delisting event table with dates, reasons, and delisting classification
5. THE Signal_Engineering_System SHALL classify each delisting as either forced or voluntary
6. THE Signal_Engineering_System SHALL flag bulk deals from delisted stocks in survivorship filter

### Requirement 33: Walk-Forward Validation Protocol

**User Story:** As a quantitative researcher, I want to use walk-forward validation, so that I can assess out-of-sample performance realistically.

#### Acceptance Criteria

1. THE Signal_Engineering_System SHALL use 24-month rolling training windows
2. THE Signal_Engineering_System SHALL use 3-month test windows for out-of-sample validation
3. THE Signal_Engineering_System SHALL advance the window by 3 months for each validation fold
4. THE Signal_Engineering_System SHALL retrain XGBoost_Model for each validation fold
5. THE Signal_Engineering_System SHALL calculate IC separately for each test window
6. THE Signal_Engineering_System SHALL aggregate IC across all test windows for final performance metric
7. THE Signal_Engineering_System SHALL maintain temporal ordering with no look-ahead bias

### Requirement 34: SHAP Feature Importance Validation

**User Story:** As a quantitative researcher, I want to validate feature importance using SHAP, so that I can identify truly predictive features.

#### Acceptance Criteria

1. WHEN a new feature is added, THE Signal_Engineering_System SHALL calculate SHAP values for the feature
2. THE Signal_Engineering_System SHALL calculate mean absolute SHAP value as feature importance metric
3. IF mean absolute SHAP value is less than 0.01, THEN THE Signal_Engineering_System SHALL flag the feature as low-importance
4. THE Signal_Engineering_System SHALL generate SHAP summary plots for top 20 features
5. THE Signal_Engineering_System SHALL validate that SHAP importance ranking aligns with IC contribution

### Requirement 35: Transaction Cost Modeling

**User Story:** As a quantitative researcher, I want to model transaction costs realistically, so that Sharpe ratio estimates reflect net returns.

#### Acceptance Criteria

1. THE Signal_Engineering_System SHALL apply 25 basis points transaction cost per round-trip trade
2. THE Signal_Engineering_System SHALL calculate turnover as percentage of portfolio changed per rebalance
3. THE Signal_Engineering_System SHALL calculate net returns as gross returns minus transaction costs
4. THE Signal_Engineering_System SHALL calculate Sharpe ratio using net returns
5. THE Signal_Engineering_System SHALL assume monthly rebalancing frequency for cost calculation

### Requirement 36: Sector Neutralization

**User Story:** As a quantitative researcher, I want to create sector dummy variables, so that the model can learn sector-specific patterns.

#### Acceptance Criteria

1. THE Signal_Engineering_System SHALL create 11 sector dummy variables based on GICS classification
2. THE Signal_Engineering_System SHALL use one-hot encoding for sector dummies
3. THE Signal_Engineering_System SHALL include sector dummies in XGBoost_Model feature set
4. THE Signal_Engineering_System SHALL map stocks to sectors using Screener sector classification
5. WHEN sector classification is missing, THE Signal_Engineering_System SHALL assign to 'Other' category

### Requirement 37: Free Float Normalization

**User Story:** As a quantitative researcher, I want to normalize bulk deal quantities by free float, so that I can compare deal significance across stocks.

#### Acceptance Criteria

1. THE Signal_Engineering_System SHALL source free float percentage from Screener shareholding data
2. THE Signal_Engineering_System SHALL calculate normalized bulk deal quantity as deal quantity divided by free float shares
3. WHEN free float data is missing, THE Signal_Engineering_System SHALL use 50% as default free float
4. THE Signal_Engineering_System SHALL apply PIT constraints using shareholding pattern date plus 2-day buffer
5. THE Signal_Engineering_System SHALL update free float data quarterly

### Requirement 38: NSE Announcement Date Scraping

**User Story:** As a quantitative researcher, I want to scrape NSE earnings announcement dates, so that I can apply precise PIT constraints for earnings data.

#### Acceptance Criteria

1. THE Signal_Engineering_System SHALL scrape earnings announcement dates from NSE corporate announcements page
2. THE Signal_Engineering_System SHALL parse announcement dates in DD-MMM-YYYY format
3. THE Signal_Engineering_System SHALL store announcement dates in a structured database table
4. WHEN scraping fails, THE Signal_Engineering_System SHALL log the error and use financial statement date plus 30 days as fallback
5. THE Signal_Engineering_System SHALL update announcement dates daily
6. THE Signal_Engineering_System SHALL validate announcement dates are not in the future

### Requirement 39: Dual-Horizon Architecture Evaluation

**User Story:** As a quantitative researcher, I want to evaluate dual-horizon prediction, so that I can optimize for different holding periods.

#### Acceptance Criteria

1. WHERE dual-horizon architecture is implemented, THE Signal_Engineering_System SHALL train separate models for 5-day and 21-day forward returns
2. WHERE dual-horizon architecture is implemented, THE Signal_Engineering_System SHALL calculate IC separately for each horizon
3. WHERE dual-horizon architecture is implemented, THE Signal_Engineering_System SHALL ensemble predictions using regime-conditional alpha blending
4. WHEN regime is risk_on_volatile, THE Signal_Engineering_System SHALL weight 5-day predictions at alpha 0.80
5. WHEN regime is risk_off_volatile, THE Signal_Engineering_System SHALL weight 5-day predictions at alpha 0.50
6. WHEN regime is risk_on_calm, THE Signal_Engineering_System SHALL weight 5-day predictions at alpha 0.65
7. WHEN regime is risk_off_calm, THE Signal_Engineering_System SHALL weight 5-day predictions at alpha 0.55
8. WHERE dual-horizon architecture is implemented, THE Signal_Engineering_System SHALL validate that ensemble IC exceeds single-horizon IC by at least 0.05
9. IF ensemble IC improvement is less than 0.05, THEN THE Signal_Engineering_System SHALL retain single 5-day model only

### Requirement 40: Temporal Convolutional Network (TCN) Implementation

**User Story:** As a quantitative researcher, I want to implement TCN models, so that I can capture temporal dependencies in feature sequences.

#### Acceptance Criteria

1. WHERE TCN is implemented, THE Signal_Engineering_System SHALL use dilated causal convolutions with dilation rates [1, 2, 4, 8]
2. WHERE TCN is implemented, THE Signal_Engineering_System SHALL use 60-day lookback windows for sequence input
3. WHERE TCN is implemented, THE Signal_Engineering_System SHALL use 4 residual blocks with 64 filters each
4. WHERE TCN is implemented, THE Signal_Engineering_System SHALL apply dropout of 0.2 for regularization
5. WHERE TCN is implemented, THE Signal_Engineering_System SHALL train using Adam optimizer with learning rate 0.001
6. WHERE TCN is implemented, THE Signal_Engineering_System SHALL use early stopping with patience of 10 epochs

### Requirement 41: Transformer Model Implementation

**User Story:** As a quantitative researcher, I want to implement Transformer models, so that I can capture long-range dependencies with attention mechanisms.

#### Acceptance Criteria

1. WHERE Transformer is implemented, THE Signal_Engineering_System SHALL use 4 attention heads
2. WHERE Transformer is implemented, THE Signal_Engineering_System SHALL use 2 encoder layers with 128 hidden dimensions
3. WHERE Transformer is implemented, THE Signal_Engineering_System SHALL apply positional encoding to sequence inputs
4. WHERE Transformer is implemented, THE Signal_Engineering_System SHALL use 60-day lookback windows
5. WHERE Transformer is implemented, THE Signal_Engineering_System SHALL apply dropout of 0.2 for regularization
6. WHERE Transformer is implemented, THE Signal_Engineering_System SHALL train using Adam optimizer with learning rate 0.0001

### Requirement 42: Model Ensemble Strategy

**User Story:** As a quantitative researcher, I want to ensemble multiple models, so that I can combine complementary predictive signals.

#### Acceptance Criteria

1. WHERE ensemble is deployed, THE Signal_Engineering_System SHALL weight XGBoost_Model predictions at 60%
2. WHERE ensemble is deployed, THE Signal_Engineering_System SHALL weight sequence model predictions at 40%
3. WHERE ensemble is deployed, THE Signal_Engineering_System SHALL calculate ensemble IC as weighted average of component ICs
4. IF ensemble IC does not exceed XGBoost_Model IC by at least 0.003, THEN THE Signal_Engineering_System SHALL retain XGBoost_Model only
5. WHERE ensemble is deployed, THE Signal_Engineering_System SHALL validate ensemble predictions are not perfectly correlated with XGBoost_Model predictions

### Requirement 43: Configuration Management and Versioning

**User Story:** As a quantitative researcher, I want to version control all configurations, so that I can reproduce experiments and track changes.

#### Acceptance Criteria

1. THE Signal_Engineering_System SHALL store all hyperparameters in version-controlled configuration files
2. THE Signal_Engineering_System SHALL tag each experiment with a unique version identifier
3. THE Signal_Engineering_System SHALL log configuration changes with timestamps and descriptions
4. THE Signal_Engineering_System SHALL maintain a changelog documenting all configuration modifications
5. THE Signal_Engineering_System SHALL enable rollback to previous configurations
6. THE Signal_Engineering_System SHALL validate configuration files against schema before execution

### Requirement 44: Diagnostic Reporting and Monitoring

**User Story:** As a quantitative researcher, I want comprehensive diagnostic reports, so that I can identify performance issues quickly.

#### Acceptance Criteria

1. THE Signal_Engineering_System SHALL generate daily diagnostic reports with IC, Sharpe ratio, and turnover
2. THE Signal_Engineering_System SHALL generate weekly feature importance reports with SHAP values
3. THE Signal_Engineering_System SHALL generate monthly regime performance reports with IC by regime
4. WHEN IC degrades by more than 0.005, THE Signal_Engineering_System SHALL trigger an alert
5. WHEN any regime IC falls below 0.010, THE Signal_Engineering_System SHALL trigger an alert
6. THE Signal_Engineering_System SHALL log all alerts with timestamps and severity levels
7. THE Signal_Engineering_System SHALL generate quarterly performance review reports with year-over-year comparisons

### Requirement 45: Data Quality Validation

**User Story:** As a quantitative researcher, I want automated data quality checks, so that I can detect data issues before they impact models.

#### Acceptance Criteria

1. THE Signal_Engineering_System SHALL validate that price data has no gaps exceeding 5 trading days
2. THE Signal_Engineering_System SHALL validate that financial data has no duplicate entries for the same period
3. THE Signal_Engineering_System SHALL validate that all features have less than 20% missing values
4. WHEN data quality validation fails, THE Signal_Engineering_System SHALL log the failure and halt model training
5. THE Signal_Engineering_System SHALL validate that all timestamps are in the past
6. THE Signal_Engineering_System SHALL validate that all numeric features are finite (no NaN or Inf values)
7. THE Signal_Engineering_System SHALL generate weekly data quality reports with validation results

### Requirement 46: Accruals Calculation Correction

**User Story:** As a quantitative researcher, I want to correct the accruals sign inversion bug, so that accruals have the correct economic interpretation.

#### Acceptance Criteria

1. THE Signal_Engineering_System SHALL calculate accruals as (Net_Income minus Operating_Cash_Flow) divided by Total_Assets
2. THE Signal_Engineering_System SHALL validate that high accruals predict higher future returns in Indian markets
3. THE Signal_Engineering_System SHALL apply unit tests validating accruals sign for known examples
4. THE Signal_Engineering_System SHALL document the accruals formula in code comments with reference to Sehgal et al. (2012) Indian market research

### Requirement 47: Regime Engine PIT Bug Fix

**User Story:** As a quantitative researcher, I want to fix the PIT bug in regime_engine.py, so that regime classifications use only historical data.

#### Acceptance Criteria

1. THE Signal_Engineering_System SHALL align regime classification dates with trading dates
2. THE Signal_Engineering_System SHALL validate that regime classifications do not use future data
3. THE Signal_Engineering_System SHALL apply unit tests validating PIT compliance for regime classifications
4. WHEN calculating Nifty_200d_SMA, THE Signal_Engineering_System SHALL use only data up to the current date

### Requirement 48: Feature Standardization Protocol

**User Story:** As a quantitative researcher, I want to standardize features within each training fold, so that I avoid look-ahead bias in normalization.

#### Acceptance Criteria

1. THE Signal_Engineering_System SHALL calculate feature means and standard deviations using training data only
2. THE Signal_Engineering_System SHALL apply training statistics to test data for standardization
3. THE Signal_Engineering_System SHALL standardize features to zero mean and unit variance
4. THE Signal_Engineering_System SHALL recalculate standardization statistics for each validation fold
5. THE Signal_Engineering_System SHALL validate that test data standardization uses no test data statistics

### Requirement 49: Missing Value Imputation Strategy

**User Story:** As a quantitative researcher, I want a consistent missing value imputation strategy, so that missing data does not introduce bias.

#### Acceptance Criteria

1. WHEN a feature has missing values, THE Signal_Engineering_System SHALL apply forward-fill using the most recent non-missing value
2. WHEN forward-fill is insufficient, THE Signal_Engineering_System SHALL apply median imputation using training data median
3. THE Signal_Engineering_System SHALL calculate imputation statistics using training data only
4. THE Signal_Engineering_System SHALL log the percentage of imputed values for each feature
5. IF a feature has more than 20% missing values, THEN THE Signal_Engineering_System SHALL flag the feature for review

### Requirement 50: Final Success Criteria Validation

**User Story:** As a quantitative researcher, I want to validate final success criteria, so that I can confirm the plan achieved its objectives.

#### Acceptance Criteria

1. WHEN all phases are complete, THE Signal_Engineering_System SHALL achieve IC greater than or equal to 0.047
2. WHEN all phases are complete, THE Signal_Engineering_System SHALL achieve Sharpe ratio greater than 0.25 after 25 basis points costs
3. FOR ALL regimes, THE Signal_Engineering_System SHALL achieve IC greater than 0.010
4. FOR ALL features, THE Leakage_Test SHALL produce IC_ratio less than 1.20
5. THE Signal_Engineering_System SHALL generate a final validation report documenting all success criteria
6. THE Signal_Engineering_System SHALL compare final IC to baseline IC and calculate total improvement
7. THE Signal_Engineering_System SHALL document all phases completed and gates passed

## Notes

### Parser and Serializer Requirements

This system includes multiple data parsing and serialization components that require special attention:

1. **NSE Announcement Date Parser**: Parses earnings announcement dates from NSE corporate announcements
   - WHEN a valid NSE announcement page is provided, THE Parser SHALL parse announcement dates into structured format
   - WHEN an invalid page is provided, THE Parser SHALL return a descriptive error
   - THE Pretty_Printer SHALL format announcement dates back into DD-MMM-YYYY format
   - FOR ALL valid announcement dates, parsing then printing then parsing SHALL produce an equivalent date (round-trip property)

2. **Financial Data Parser**: Parses quarterly and annual financial statements from Screener
   - WHEN valid financial data is provided, THE Parser SHALL parse it into structured financial objects
   - THE Pretty_Printer SHALL format financial objects back into valid CSV format
   - FOR ALL valid financial data, parsing then printing then parsing SHALL produce equivalent values (round-trip property)

3. **Bulk Deal Parser**: Parses bulk deal transaction data from NSE/BSE
   - WHEN valid bulk deal data is provided, THE Parser SHALL parse it into structured transaction objects
   - FOR ALL valid bulk deals, parsing then printing then parsing SHALL produce equivalent transactions (round-trip property)

These round-trip properties are ESSENTIAL for data integrity validation and should be tested with property-based testing frameworks.
