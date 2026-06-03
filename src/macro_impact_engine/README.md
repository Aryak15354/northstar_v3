# Macro Impact Engine (MIE)

## What is this?

An institutional-grade system that reveals **which RBI macro variables affect which companies, at what lag, with what magnitude, and how stable those relationships are**.

This is not a signal. This is a **Causal Macro Sensitivity Engine** for macro attribution research.

## Quick Example

```python
from src.macro_impact_engine import MacroDataLoader, LaggedRegressionEngine

# Load data
loader = MacroDataLoader()
data = loader.load_all(start_date="2018-01-01")

# Run analysis
engine = LaggedRegressionEngine()
results = engine.run_all_companies(
    data['returns'],
    data['macro'],
    data['market']
)

# Get SBIN macro fingerprint
sbin_result = results['SBIN.NS']
print(f"R²: {sbin_result['r_squared']:.3f}")
print(f"Significant factors: {sbin_result['n_significant']}")
```

## What You Get

### Company-Level Insights

```
Company: SBIN.NS
---------------------------------
Top Macro Drivers:
  1. Liquidity (lag 8 weeks)
     Beta: +0.45
     Stability: 0.62
     Crisis Sensitivity: High
  
  2. Yield Curve (lag 4 weeks)
     Beta: -0.31
  
  3. CPI (lag 12 weeks)
     Beta: -0.22

Macro Exposure Score:
   Pro-Credit Cycle Stock
```

### Sector-Level Insights

```
Sector: Financials
---------------------------------
Most Impactful Variables:
- Non-food credit growth
- Repo rate changes
- 10Y G-Sec yield

Lag Structure:
- 4–8 weeks typical transmission
```

### Portfolio-Level Insights

```
Portfolio Macro Exposure:
- Liquidity Beta: +0.35 (HIGH)
- Rate Beta: -0.22 (MODERATE)
- FX Beta: +0.15 (LOW)

Risk: Vulnerable to liquidity shocks
```

## Components

1. **data_loader.py**: Load RBI + company data
2. **preprocessing.py**: Stationarize, standardize, construct lags
3. **lagged_regression.py**: Multi-lag OLS with HAC standard errors
4. **granger_tests.py**: Test predictive causality
5. **rolling_beta.py**: Time-varying sensitivities
6. **stability_tests.py**: Structural break detection
7. **sector_aggregation.py**: Sector-level aggregation
8. **report_generator.py**: Institutional reports

## Statistical Rigor

✅ Stationarity testing (ADF)  
✅ Newey-West HAC standard errors  
✅ FDR multiple testing correction  
✅ Granger causality tests  
✅ Rolling window stability  
✅ Regime-conditional estimation  

## Integration with Northstar V3

### Portfolio Governor
Reduce exposure when portfolio overloaded to certain macro factor

### Risk Authority
Auto-reduce if liquidity shock probability rises and portfolio has high liquidity beta

### Alpha Engine
Boost signal weight when stock has strong positive beta to rising macro factor

## Run Demo

```bash
python examples/macro_impact_engine_demo.py
```

## Documentation

See `docs/MACRO_IMPACT_ENGINE_GUIDE.md` for complete documentation.

## Output Location

All reports saved to: `reports/macro_impact/`

- `company_fingerprints.json`
- `sector_macro_sensitivity.json`
- `company_macro_betas.csv`
- `sector_macro_betas.csv`
- `sector_macro_heatmap.csv`

## Requirements

- pandas
- numpy
- scipy
- statsmodels
- scikit-learn

## Status

✅ Production Ready  
📊 Tested on 855 RBI variables × 500 companies  
🏛️ Institutional-grade statistical controls  
