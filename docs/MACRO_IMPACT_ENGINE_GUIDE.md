# 🧠 Macro Impact Engine (MIE) - Complete Guide

## Overview

The Macro Impact Engine is an institutional-grade macro-equity transmission system that reveals causal relationships between RBI macro variables and company returns.

### Key Questions Answered

1. **Which RBI variable affects which company?**
2. **At what lag?**
3. **With what sign and magnitude?**
4. **How stable is that relationship?**
5. **How does it vary by regime?**

## Architecture

```
northstar_v3/
├── src/macro_impact_engine/
│   ├── __init__.py
│   ├── data_loader.py          # Load RBI + company data
│   ├── preprocessing.py         # Stationarize, standardize, lag construction
│   ├── lagged_regression.py    # Multi-lag OLS estimation
│   ├── granger_tests.py        # Predictive causality testing
│   ├── rolling_beta.py         # Time-varying sensitivities
│   ├── stability_tests.py      # Structural break detection
│   ├── sector_aggregation.py   # Sector-level aggregation
│   └── report_generator.py     # Institutional reports
└── reports/macro_impact/        # Output directory
```

## Mathematical Specification

### Base Regression Model

For each company `i`:

```
R_{i,t} = α_i + Σ_{k,l} β_{i,k,l} M_{k,t-l} + γ_i R_{market,t} + ε_{i,t}
```

Where:
- `R_{i,t}` = company return at time t
- `M_{k,t-l}` = macro variable k at lag l
- `R_{market,t}` = market return (control)
- `β_{i,k,l}` = macro sensitivity coefficient
- `ε_{i,t}` = error term

### Matrix Form

```
R_i = X θ_i + ε_i
θ_i = (X'X)^{-1} X'R_i  (OLS estimator)
```

### Lag Structure

Test lags: `l ∈ {0, 1, 2, 4, 8, 12, 26}` weeks

Optimal lag = lag with highest |t-statistic|

### Rolling Stability

```
β_{i,k,t}^{rolling} = estimated over window [t-W, t]

Stability = std(β_{rolling}) / |mean(β_{rolling})|
```

Low stability = stable relationship  
High stability = regime-dependent

### Statistical Controls

1. **Stationarity**: ADF test + differencing
2. **Standardization**: Z-score normalization
3. **Outlier Control**: Winsorization at 1%
4. **Robust SE**: Newey-West HAC standard errors
5. **Multiple Testing**: Benjamini-Hochberg FDR correction

## Usage

### Quick Start

```python
from src.macro_impact_engine import (
    MacroDataLoader,
    MacroPreprocessor,
    LaggedRegressionEngine,
    SectorAggregator,
    MacroImpactReportGenerator
)

# 1. Load data
loader = MacroDataLoader(target_frequency='W')
data = loader.load_all(start_date="2018-01-01")

# 2. Preprocess
preprocessor = MacroPreprocessor(lags=[0, 1, 2, 4, 8, 12])
macro_processed, _ = preprocessor.preprocess_macro(data['macro'])
returns_processed = preprocessor.preprocess_returns(data['returns'])

# 3. Run regressions
engine = LaggedRegressionEngine()
results = engine.run_all_companies(
    returns_processed,
    macro_processed,
    data['market']
)

# 4. Extract betas
betas = engine.extract_macro_betas(results, 'repo_rate')

# 5. Aggregate to sectors
aggregator = SectorAggregator()
sector_betas = aggregator.aggregate_to_sector(betas, data['sector_map'])

# 6. Generate reports
report_gen = MacroImpactReportGenerator()
fingerprint = report_gen.generate_company_fingerprint('SBIN.NS', results['SBIN.NS'])
```

### Run Demo

```bash
python examples/macro_impact_engine_demo.py
```

## Output Reports

### 1. Company Macro Fingerprint

```json
{
  "ticker": "SBIN.NS",
  "n_obs": 260,
  "r_squared": 0.45,
  "n_significant": 12,
  "top_drivers": [
    {
      "variable": "liquidity_lag8",
      "beta": 0.45,
      "t_stat": 5.2,
      "p_value": 0.001
    },
    {
      "variable": "repo_rate_lag4",
      "beta": -0.31,
      "t_stat": -3.8,
      "p_value": 0.003
    }
  ]
}
```

### 2. Sector Macro Sensitivity

```json
{
  "sector": "Financials",
  "n_companies": 25,
  "top_macro_drivers": [
    {
      "macro_variable": "liquidity",
      "lag": 8,
      "beta": 0.42,
      "t_stat": 4.5
    },
    {
      "macro_variable": "yield_curve",
      "lag": 4,
      "beta": -0.28,
      "t_stat": -3.2
    }
  ]
}
```

### 3. Portfolio Macro Exposure

```json
{
  "portfolio_size": 50,
  "macro_exposures": [
    {
      "macro_variable": "liquidity",
      "portfolio_beta": 0.35,
      "n_holdings": 45
    },
    {
      "macro_variable": "repo_rate",
      "portfolio_beta": -0.22,
      "n_holdings": 42
    }
  ]
}
```

## Integration with Northstar V3

### 1. Portfolio Governor

```python
# Reduce exposure when portfolio overloaded to macro factor
if portfolio_macro_drag < -threshold:
    exposure_multiplier *= (1 - adjustment_factor)
```

### 2. Risk Authority

```python
# Auto-reduce if liquidity shock + high liquidity beta
if liquidity_shock_prob > 0.7 and portfolio_liquidity_beta > 0.5:
    trigger_risk_reduction()
```

### 3. Alpha Engine

```python
# Boost signal weight if favorable macro alignment
if stock_liquidity_beta > 0 and liquidity_rising:
    signal_weight *= macro_boost_factor
```

## Advanced Features

### Granger Causality Testing

```python
from src.macro_impact_engine import GrangerCausalityTester

tester = GrangerCausalityTester(max_lags=12)
result = tester.granger_test(company_returns, macro_variable)

if result['granger_causes']:
    print(f"Macro variable predicts returns at lag {result['best_lag']}")
```

### Rolling Beta Estimation

```python
from src.macro_impact_engine import RollingBetaEstimator

estimator = RollingBetaEstimator(window_sizes=[156, 260])
rolling_results = estimator.estimate_all_windows(company_returns, macro_variable)

stability = rolling_results[156]['stability']
print(f"Stability metric: {stability['stability']:.2f}")
```

### Structural Break Detection

```python
from src.macro_impact_engine import StabilityAnalyzer

analyzer = StabilityAnalyzer()
chow_result = analyzer.chow_test(
    company_returns,
    macro_variable,
    breakpoint=pd.Timestamp('2020-03-01')  # COVID crisis
)

if chow_result['structural_break']:
    print(f"Beta before: {chow_result['beta_before']:.3f}")
    print(f"Beta after: {chow_result['beta_after']:.3f}")
```

## Performance Optimization

### Dimensionality Reduction

For 855 macro variables, use PCA:

```python
from sklearn.decomposition import PCA

# Reduce to 20 macro factors
pca = PCA(n_components=20)
macro_factors = pca.fit_transform(macro_processed)
```

### Parallel Processing

```python
from joblib import Parallel, delayed

results = Parallel(n_jobs=-1)(
    delayed(engine.run_company_regression)(
        returns_df[ticker],
        macro_processed,
        market_factor,
        ticker
    )
    for ticker in tickers
)
```

## Validation Checklist

- [ ] Stationarity confirmed (ADF test p < 0.05)
- [ ] Multicollinearity checked (VIF < 10)
- [ ] Autocorrelation tested (Durbin-Watson)
- [ ] Heteroskedasticity controlled (HAC SE)
- [ ] Multiple testing corrected (FDR)
- [ ] Out-of-sample validation performed
- [ ] Economic interpretation verified

## Common Pitfalls

1. **Non-stationary data**: Always test and transform
2. **Look-ahead bias**: Use point-in-time data only
3. **Overfitting**: Apply FDR correction
4. **Spurious correlation**: Test Granger causality
5. **Regime instability**: Check rolling betas

## References

- Newey, W. K., & West, K. D. (1987). HAC standard errors
- Benjamini, Y., & Hochberg, Y. (1995). FDR control
- Granger, C. W. J. (1969). Causality testing
- Chow, G. C. (1960). Structural break tests

## Support

For questions or issues:
- Check examples/macro_impact_engine_demo.py
- Review test cases in tests/
- Consult Northstar V3 documentation

---

**Version**: 1.0.0  
**Last Updated**: 2026-02-15  
**Status**: Production Ready
