# Requirements Document: Probabilistic Forecasting Spine

## Introduction

The Probabilistic Forecasting Spine is a 6-layer institutional-grade forecasting framework for the Northstar options trading system. Unlike traditional price prediction systems, this framework forecasts the RIGHT objects: cross-sectional expected returns, volatility, regime transitions, and tail risk probabilities. The system emphasizes stability over complexity, proper calibration discipline, and realistic performance expectations (IC: 0.03-0.06, Sharpe: 1-1.8).

## Glossary

- **Forecast_Engine**: The core probabilistic forecasting system that outputs distribution parameters
- **Signal_Layer**: Component that builds orthogonal signals across 5 buckets (Trend/Momentum, Valuation, Quality, Liquidity/Microstructure, Cross-Asset/Macro)
- **Feature_Engine**: Component that contextualizes signals with regime awareness
- **Core_Forecast_Model**: Probabilistic models (Ridge Regression for cross-section, HAR for volatility, Logistic for tail probability)
- **Calibration_Monitor**: Component that tracks forecast accuracy and drift over time
- **Decay_Monitor**: Component that detects signal degradation and model drift
- **Market_Brain**: Existing Northstar component that provides regime probabilities
- **Capital_Allocator**: Existing Northstar component that converts distributions to portfolio weights
- **Portfolio_Governor**: Existing Northstar component that applies portfolio constraints
- **Risk_Authority**: Existing Northstar component that overrides decisions based on risk thresholds
- **IC**: Information Coefficient - correlation between forecast and realized outcome
- **HAR**: Heterogeneous Autoregressive model for volatility forecasting
- **CVaR**: Conditional Value at Risk - expected loss beyond VaR threshold
- **Walk_Forward_Validation**: Time-series validation method that prevents look-ahead bias

## Requirements

### Requirement 1: Cross-Sectional Expected Return Forecasting

**User Story:** As a portfolio manager, I want to forecast 10-day excess returns relative to the universe mean, so that I can identify relative value opportunities without market timing.

#### Acceptance Criteria

1. WHEN the Forecast_Engine receives market state, THE Forecast_Engine SHALL output E[r_i,t+10 | state_t] for each asset i
2. WHEN computing excess returns, THE Forecast_Engine SHALL calculate returns relative to universe mean, not absolute returns
3. WHEN generating forecasts, THE Core_Forecast_Model SHALL use ridge regression with cross-sectional normalization
4. WHEN the forecast horizon is reached, THE Calibration_Monitor SHALL record realized excess returns for validation
5. THE Forecast_Engine SHALL output full distribution parameters (mean, variance) not point estimates

### Requirement 2: Volatility Forecasting

**User Story:** As an options trader, I want to forecast 10-day realized volatility, so that I can price options accurately and manage risk.

#### Acceptance Criteria

1. WHEN the Forecast_Engine receives market state, THE Forecast_Engine SHALL output E[σ_i,t+10 | state_t] for each asset i
2. WHEN modeling volatility, THE Core_Forecast_Model SHALL use HAR (Heterogeneous Autoregressive) model with regime features
3. WHEN volatility forecasts are generated, THE Forecast_Engine SHALL provide them to the options pricing engine
4. WHEN volatility forecasts are generated, THE Forecast_Engine SHALL provide them to the Risk_Authority for position sizing
5. THE Forecast_Engine SHALL output volatility distribution parameters including uncertainty estimates

### Requirement 3: Regime Transition Probability Forecasting

**User Story:** As a risk manager, I want to forecast the probability of regime changes, so that I can adjust portfolio positioning before transitions occur.

#### Acceptance Criteria

1. WHEN the Forecast_Engine receives current regime state, THE Forecast_Engine SHALL output P(regime_t+10 ≠ regime_t)
2. WHEN computing regime transition probability, THE Core_Forecast_Model SHALL use forward-looking prediction, not classification of current regime
3. WHEN regime transition probability exceeds threshold, THE Forecast_Engine SHALL signal the Capital_Allocator to adjust positioning
4. THE Forecast_Engine SHALL integrate with Market_Brain to receive current regime probabilities as input

### Requirement 4: Tail Risk Probability Forecasting

**User Story:** As a risk manager, I want to forecast the probability of extreme losses, so that I can allocate capital conservatively when tail risk is elevated.

#### Acceptance Criteria

1. WHEN the Forecast_Engine receives market state, THE Forecast_Engine SHALL output P(r_i,t+10 < -2σ) for each asset i
2. WHEN computing tail probability, THE Core_Forecast_Model SHALL use logistic regression with regime-dependent features
3. WHEN tail probability exceeds threshold, THE Risk_Authority SHALL override position sizing or block trades
4. THE Forecast_Engine SHALL provide tail probability to Capital_Allocator for CVaR constraint enforcement

### Requirement 5: Signal Layer Construction

**User Story:** As a quantitative researcher, I want to build orthogonal signals across multiple categories, so that I can capture diverse sources of alpha without redundancy.

#### Acceptance Criteria

1. THE Signal_Layer SHALL construct signals in exactly 5 buckets: Trend/Momentum, Valuation, Quality, Liquidity/Microstructure, Cross-Asset/Macro
2. WHEN constructing signals within a bucket, THE Signal_Layer SHALL ensure signals are orthogonal (correlation < 0.3)
3. WHEN combining signals across buckets, THE Signal_Layer SHALL apply equal weighting within buckets before cross-bucket combination
4. THE Signal_Layer SHALL compute signals using only information available at time t (no look-ahead bias)
5. WHEN a signal cannot be computed due to missing data, THE Signal_Layer SHALL handle it gracefully without breaking the pipeline

### Requirement 6: Feature Engine with Regime Awareness

**User Story:** As a quantitative researcher, I want to contextualize signals with regime information, so that signal interpretation adapts to market conditions.

#### Acceptance Criteria

1. WHEN the Feature_Engine receives signals, THE Feature_Engine SHALL augment them with current regime probabilities from Market_Brain
2. WHEN the Feature_Engine receives signals, THE Feature_Engine SHALL create regime-interaction features (signal × regime_probability)
3. WHEN regime probabilities change, THE Feature_Engine SHALL recompute contextualized features
4. THE Feature_Engine SHALL normalize features to prevent scale dominance in downstream models
5. THE Feature_Engine SHALL output feature matrix with proper time alignment (no look-ahead)

### Requirement 7: Ridge Regression Cross-Sectional Model

**User Story:** As a quantitative researcher, I want to use ridge regression for cross-sectional return forecasting, so that I can regularize against overfitting while maintaining interpretability.

#### Acceptance Criteria

1. WHEN the Core_Forecast_Model trains cross-sectional model, THE Core_Forecast_Model SHALL use ridge regression with L2 penalty
2. WHEN selecting regularization parameter λ, THE Core_Forecast_Model SHALL use walk-forward validation without look-ahead bias
3. WHEN computing predictions, THE Core_Forecast_Model SHALL apply cross-sectional normalization (demean and scale by cross-sectional std)
4. THE Core_Forecast_Model SHALL output both point forecast and forecast uncertainty (prediction interval)
5. WHEN training data is insufficient, THE Core_Forecast_Model SHALL use Bayesian ridge with informative priors

### Requirement 8: HAR Volatility Model

**User Story:** As a volatility trader, I want to use HAR model for volatility forecasting, so that I can capture multi-horizon volatility dynamics.

#### Acceptance Criteria

1. WHEN the Core_Forecast_Model forecasts volatility, THE Core_Forecast_Model SHALL use HAR model with daily, weekly, and monthly components
2. WHEN constructing HAR features, THE Core_Forecast_Model SHALL include regime-dependent coefficients
3. WHEN computing realized volatility for validation, THE Core_Forecast_Model SHALL use proper forward-looking windows (no overlap)
4. THE Core_Forecast_Model SHALL output volatility forecast distribution (mean and variance)
5. WHEN volatility regime changes, THE Core_Forecast_Model SHALL adapt coefficients based on regime state

### Requirement 9: Logistic Tail Probability Model

**User Story:** As a risk manager, I want to use logistic regression for tail probability forecasting, so that I can estimate extreme event likelihood with proper calibration.

#### Acceptance Criteria

1. WHEN the Core_Forecast_Model forecasts tail probability, THE Core_Forecast_Model SHALL use logistic regression with regime features
2. WHEN defining tail events, THE Core_Forecast_Model SHALL use -2σ threshold relative to forecasted volatility
3. WHEN training logistic model, THE Core_Forecast_Model SHALL handle class imbalance using appropriate weighting
4. THE Core_Forecast_Model SHALL output calibrated probabilities (not raw logit scores)
5. WHEN tail events are rare, THE Core_Forecast_Model SHALL use regularization to prevent overfitting

### Requirement 10: Calibration Monitoring

**User Story:** As a quantitative researcher, I want to track forecast accuracy over time, so that I can detect when models need retraining or replacement.

#### Acceptance Criteria

1. WHEN forecasts are generated, THE Calibration_Monitor SHALL record forecast values and timestamps
2. WHEN forecast horizons are reached, THE Calibration_Monitor SHALL compute realized outcomes and forecast errors
3. THE Calibration_Monitor SHALL compute rolling IC (Information Coefficient) over trailing 60-day window
4. WHEN rolling IC falls below 0.02, THE Calibration_Monitor SHALL alert that signal strength is insufficient
5. THE Calibration_Monitor SHALL compute calibration metrics (forecast distribution vs realized distribution)

### Requirement 11: Decay Detection

**User Story:** As a quantitative researcher, I want to detect signal degradation, so that I can identify when alpha sources have decayed.

#### Acceptance Criteria

1. THE Decay_Monitor SHALL compute stability ratio (IC_recent / IC_historical)
2. WHEN stability ratio falls below 0.7, THE Decay_Monitor SHALL alert that signal is degrading
3. THE Decay_Monitor SHALL track regime-dependent IC to detect regime-specific decay
4. THE Decay_Monitor SHALL validate signal survival through crisis periods (2008, 2020)
5. WHEN signal decay is detected, THE Decay_Monitor SHALL recommend signal replacement or retraining

### Requirement 12: Walk-Forward Validation

**User Story:** As a quantitative researcher, I want to validate models using walk-forward methodology, so that I can ensure no look-ahead bias in performance estimates.

#### Acceptance Criteria

1. WHEN validating models, THE Core_Forecast_Model SHALL use rolling walk-forward windows
2. WHEN selecting hyperparameters, THE Core_Forecast_Model SHALL use only data available at training time
3. WHEN computing validation metrics, THE Core_Forecast_Model SHALL use only out-of-sample forecasts
4. THE Core_Forecast_Model SHALL maintain strict time ordering (train on t-N:t, validate on t+1:t+h)
5. WHEN expanding training window, THE Core_Forecast_Model SHALL check for structural breaks

### Requirement 13: Bayesian Hierarchical Extensions

**User Story:** As a quantitative researcher, I want to use Bayesian hierarchical models for parameter uncertainty, so that I can quantify forecast confidence properly.

#### Acceptance Criteria

1. WHERE Bayesian extension is enabled, THE Core_Forecast_Model SHALL use hierarchical priors for cross-sectional parameters
2. WHERE Bayesian extension is enabled, THE Core_Forecast_Model SHALL output posterior distributions for parameters
3. WHERE Bayesian extension is enabled, THE Core_Forecast_Model SHALL propagate parameter uncertainty to forecast uncertainty
4. WHEN prior information is available, THE Core_Forecast_Model SHALL incorporate it through informative priors
5. WHERE Bayesian extension is enabled, THE Core_Forecast_Model SHALL use MCMC or variational inference for posterior computation

### Requirement 14: Signal Strength Validation

**User Story:** As a quantitative researcher, I want to validate signal strength before deploying complex models, so that I don't waste resources on weak signals.

#### Acceptance Criteria

1. WHEN evaluating signal strength, THE Calibration_Monitor SHALL compute rolling IC over multiple time windows
2. WHEN IC is below 0.02-0.03, THE Calibration_Monitor SHALL reject signal as too weak for deployment
3. WHEN stability ratio is below 0.7, THE Calibration_Monitor SHALL reject signal as too unstable
4. THE Calibration_Monitor SHALL compute regime-dependent IC differences to validate regime adaptation
5. THE Calibration_Monitor SHALL validate signal survival through crisis periods before production deployment

### Requirement 15: Integration with Market Brain

**User Story:** As a system architect, I want to integrate with Market_Brain for regime information, so that forecasts can adapt to market conditions.

#### Acceptance Criteria

1. WHEN the Forecast_Engine initializes, THE Forecast_Engine SHALL establish connection to Market_Brain
2. WHEN generating forecasts, THE Forecast_Engine SHALL query Market_Brain for current regime probabilities
3. WHEN Market_Brain updates regime probabilities, THE Forecast_Engine SHALL receive notifications
4. IF Market_Brain is unavailable, THEN THE Forecast_Engine SHALL use cached regime probabilities with staleness warning
5. THE Forecast_Engine SHALL validate regime probability format (probabilities sum to 1, all non-negative)

### Requirement 16: Integration with Capital Allocator

**User Story:** As a portfolio manager, I want to provide forecast distributions to Capital_Allocator, so that portfolio weights can be optimized under uncertainty.

#### Acceptance Criteria

1. WHEN forecasts are generated, THE Forecast_Engine SHALL output distribution parameters to Capital_Allocator
2. WHEN Capital_Allocator requests forecasts, THE Forecast_Engine SHALL provide mean-variance parameters for mean-variance optimization
3. WHEN Capital_Allocator requests forecasts, THE Forecast_Engine SHALL provide tail probabilities for CVaR constraints
4. THE Forecast_Engine SHALL provide forecast covariance matrix for portfolio optimization
5. WHEN forecast uncertainty is high, THE Forecast_Engine SHALL signal Capital_Allocator to reduce position sizes

### Requirement 17: Integration with Risk Authority

**User Story:** As a risk manager, I want Risk_Authority to override trades when tail risk is elevated, so that capital is protected during extreme conditions.

#### Acceptance Criteria

1. WHEN tail probability exceeds threshold, THE Forecast_Engine SHALL notify Risk_Authority
2. WHEN Risk_Authority queries tail risk, THE Forecast_Engine SHALL provide current tail probability estimates
3. WHEN Risk_Authority overrides position sizing, THE Forecast_Engine SHALL log the override for audit
4. THE Forecast_Engine SHALL provide volatility forecasts to Risk_Authority for position sizing
5. IF tail probability data is stale, THEN THE Forecast_Engine SHALL prevent Risk_Authority from using it

### Requirement 18: Performance Expectations and Validation

**User Story:** As a quantitative researcher, I want to validate realistic performance expectations, so that I can set appropriate targets and detect anomalies.

#### Acceptance Criteria

1. THE Calibration_Monitor SHALL validate directional accuracy is between 52-57%
2. THE Calibration_Monitor SHALL validate IC is between 0.03-0.06
3. THE Calibration_Monitor SHALL validate Sharpe ratio is between 1-1.8
4. WHEN max drawdown exceeds 20%, THE Calibration_Monitor SHALL alert that risk layer may be failing
5. WHEN performance metrics exceed realistic bounds, THE Calibration_Monitor SHALL flag potential overfitting or data leakage

### Requirement 19: Crisis Stress Framework

**User Story:** As a risk manager, I want to stress-test forecasts under crisis scenarios, so that I can validate robustness during extreme conditions.

#### Acceptance Criteria

1. THE Calibration_Monitor SHALL validate forecast performance during 2008 financial crisis period
2. THE Calibration_Monitor SHALL validate forecast performance during 2020 COVID crash period
3. WHEN crisis conditions are detected, THE Forecast_Engine SHALL increase forecast uncertainty
4. THE Calibration_Monitor SHALL compute crisis-conditional IC to validate crisis adaptation
5. WHEN crisis stress tests fail, THE Calibration_Monitor SHALL prevent production deployment

### Requirement 20: Hyperparameter Selection Without Leakage

**User Story:** As a quantitative researcher, I want to select hyperparameters without look-ahead bias, so that validation metrics are honest.

#### Acceptance Criteria

1. WHEN selecting hyperparameters, THE Core_Forecast_Model SHALL use only training data available at time t
2. WHEN validating hyperparameter choices, THE Core_Forecast_Model SHALL use walk-forward out-of-sample data
3. THE Core_Forecast_Model SHALL maintain separate validation set that is never used for hyperparameter tuning
4. WHEN hyperparameter search is complete, THE Core_Forecast_Model SHALL report out-of-sample performance on held-out test set
5. THE Core_Forecast_Model SHALL log all hyperparameter choices with timestamps for audit trail

### Requirement 21: Forecast Output Format

**User Story:** As a system integrator, I want standardized forecast output format, so that downstream components can consume forecasts reliably.

#### Acceptance Criteria

1. THE Forecast_Engine SHALL output forecasts in standardized JSON format with schema validation
2. WHEN outputting cross-sectional forecasts, THE Forecast_Engine SHALL include asset identifier, timestamp, mean, variance, and confidence interval
3. WHEN outputting volatility forecasts, THE Forecast_Engine SHALL include asset identifier, timestamp, volatility mean, volatility variance, and horizon
4. WHEN outputting tail probabilities, THE Forecast_Engine SHALL include asset identifier, timestamp, probability, threshold, and confidence interval
5. WHEN outputting regime transition probabilities, THE Forecast_Engine SHALL include current regime, target regime, probability, and horizon

### Requirement 22: Logging and Audit Trail

**User Story:** As a compliance officer, I want comprehensive logging of all forecasts and model decisions, so that I can audit system behavior.

#### Acceptance Criteria

1. WHEN forecasts are generated, THE Forecast_Engine SHALL log all input features, model parameters, and output forecasts
2. WHEN models are retrained, THE Forecast_Engine SHALL log training data range, hyperparameters, and validation metrics
3. WHEN signal decay is detected, THE Decay_Monitor SHALL log decay metrics and recommended actions
4. WHEN Risk_Authority overrides occur, THE Forecast_Engine SHALL log override reason and tail probability
5. THE Forecast_Engine SHALL maintain audit trail with immutable timestamps for regulatory compliance

### Requirement 23: Error Handling and Graceful Degradation

**User Story:** As a system operator, I want the system to handle errors gracefully, so that partial failures don't cascade to full system failure.

#### Acceptance Criteria

1. WHEN Market_Brain is unavailable, THE Forecast_Engine SHALL use cached regime probabilities with staleness warning
2. WHEN signal computation fails for one asset, THE Forecast_Engine SHALL continue processing other assets
3. WHEN model training fails, THE Forecast_Engine SHALL fall back to previous model version
4. WHEN forecast uncertainty is too high, THE Forecast_Engine SHALL output conservative forecasts (shrink toward zero)
5. IF critical component fails, THEN THE Forecast_Engine SHALL notify operators and enter safe mode (no new forecasts)

### Requirement 24: Configuration and Parameterization

**User Story:** As a system operator, I want to configure forecast parameters without code changes, so that I can tune the system in production.

#### Acceptance Criteria

1. THE Forecast_Engine SHALL load configuration from YAML file at startup
2. WHEN configuration changes, THE Forecast_Engine SHALL reload configuration without restart
3. THE Forecast_Engine SHALL validate configuration parameters against schema before applying
4. THE Forecast_Engine SHALL support environment-specific configurations (dev, staging, production)
5. WHEN invalid configuration is detected, THE Forecast_Engine SHALL reject it and log error without crashing

### Requirement 25: Performance and Latency Requirements

**User Story:** As a system operator, I want forecasts generated within latency budget, so that trading decisions can be made in real-time.

#### Acceptance Criteria

1. WHEN generating forecasts for full universe, THE Forecast_Engine SHALL complete within 5 seconds
2. WHEN generating single-asset forecast, THE Forecast_Engine SHALL complete within 100 milliseconds
3. WHEN model retraining is triggered, THE Core_Forecast_Model SHALL complete within 60 seconds
4. THE Forecast_Engine SHALL cache intermediate computations to reduce latency
5. WHEN latency budget is exceeded, THE Forecast_Engine SHALL log performance warning and identify bottleneck
