# Volatility Processing Migration Guide

## Overview

Volatility processing components have been consolidated into:
**`src/volatility/volatility_processor.py`**

This provides utility functions for calculating realized volatility metrics that feed into the VolatilityStateEngine.

## Archived Components

1. **`volatility_engine_v1.py`** (from `src/processing/volatility_engine.py`)
   - Realized volatility calculation
   - Volatility percentile ranking
   - ATR calculation
   - Volatility regime classification

2. **`options_volatility_v1.py`** (from `src/processing/options_volatility.py`)
   - Simplified realized volatility calculation
   - ATR calculation for options

## New Unified API

### Import Changes

**Old:**
```python
# Scripts that directly ran volatility calculations
# No imports - standalone scripts
```

**New:**
```python
from src.volatility.volatility_processor import (
    calculate_realized_volatility,
    calculate_atr,
    classify_volatility_regime,
    process_ticker_volatility,
    process_universe_volatility,
)
```

### Basic Usage

**Old (volatility_engine.py):**
```python
# Standalone script
import pandas as pd
import numpy as np

df = pd.read_parquet("data/processed/prices.parquet")
df = df.sort_values(["ticker", "Date"])

records = []
for ticker, g in df.groupby("ticker"):
    g["ret"] = g["Close"].pct_change()
    g["vol"] = g["ret"].rolling(30).std() * np.sqrt(252)
    g["atr"] = (g["High"] - g["Low"]).rolling(14).mean()
    # ... more processing
    
out = pd.DataFrame(records)
out.to_parquet("data/processed/volatility_state.parquet", index=False)
```

**New:**
```python
from src.volatility.volatility_processor import process_universe_volatility
import pandas as pd

# Load prices
prices_df = pd.read_parquet("data/processed/prices.parquet")

# Process all tickers
volatility_metrics = process_universe_volatility(
    prices_df,
    vol_window=30,
    atr_window=14,
    percentile_window=252
)

# Save results
volatility_metrics.to_parquet("data/processed/volatility_state.parquet", index=False)
```

### Single Ticker Processing

**Old:**
```python
# Manual calculation for each ticker
for ticker, g in df.groupby("ticker"):
    g["ret"] = g["Close"].pct_change()
    g["vol"] = g["ret"].rolling(30).std() * np.sqrt(252)
    latest_vol = g["vol"].iloc[-1]
```

**New:**
```python
from src.volatility.volatility_processor import process_ticker_volatility

# Get ticker data
ticker_data = df[df['ticker'] == 'AAPL']

# Calculate metrics
metrics = process_ticker_volatility(
    ticker_data,
    vol_window=30,
    atr_window=14
)

# Access results
realized_vol = metrics['realized_vol']
vol_percentile = metrics['volatility_percentile']
atr = metrics['atr']
regime = metrics['volatility_regime']
```

## Function Mapping

### Realized Volatility

**Old:**
```python
g["ret"] = g["Close"].pct_change()
g["vol"] = g["ret"].rolling(30).std() * np.sqrt(252)
```

**New:**
```python
from src.volatility.volatility_processor import calculate_realized_volatility

vol = calculate_realized_volatility(
    prices=ticker_data['Close'],
    window=30,
    annualization_factor=252.0
)
```

### ATR (Average True Range)

**Old:**
```python
g["atr"] = (g["High"] - g["Low"]).rolling(14).mean()
```

**New:**
```python
from src.volatility.volatility_processor import calculate_atr

atr = calculate_atr(
    high=ticker_data['High'],
    low=ticker_data['Low'],
    window=14
)
```

### Volatility Regime Classification

**Old:**
```python
g["vol_pct"] = g["vol"].rank(pct=True)
latest = g.tail(1).iloc[0]

if latest["vol_pct"] < 0.33:
    regime = "Low"
elif latest["vol_pct"] < 0.66:
    regime = "Normal"
else:
    regime = "High"
```

**New:**
```python
from src.volatility.volatility_processor import classify_volatility_regime

regime = classify_volatility_regime(
    current_vol=current_vol,
    vol_history=vol_history,
    low_threshold=0.33,
    high_threshold=0.66
)
```

### Volatility Percentile

**Old:**
```python
g["vol_pct"] = g["vol"].rank(pct=True)
```

**New:**
```python
from src.volatility.volatility_processor import calculate_volatility_percentile

vol_pct = calculate_volatility_percentile(
    current_vol=current_vol,
    vol_history=vol_history
)
```

## New Features

### Implied-Realized Spread

Calculate the spread between implied and realized volatility:

```python
from src.volatility.volatility_processor import calculate_implied_realized_spread

spread = calculate_implied_realized_spread(
    implied_vol=0.25,
    realized_vol=0.20
)
# spread = 0.05 (implied is 5% higher than realized)
```

### Volatility Risk Premium

Calculate the volatility risk premium:

```python
from src.volatility.volatility_processor import calculate_volatility_risk_premium

vrp = calculate_volatility_risk_premium(
    implied_vol=0.25,
    realized_vol=0.20
)
# vrp = 0.20 (20% risk premium)
```

## Integration with VolatilityStateEngine

The volatility processor functions are designed to feed into the VolatilityStateEngine:

```python
from src.volatility import VolatilityStateEngine
from src.volatility.volatility_processor import process_universe_volatility

# Calculate volatility metrics
vol_metrics = process_universe_volatility(prices_df)

# Update state engine
state_engine = VolatilityStateEngine()

for _, row in vol_metrics.iterrows():
    state_engine.update_realized_volatility(
        ticker=row['ticker'],
        realized_vol=row['realized_vol'],
        vol_percentile=row['volatility_percentile']
    )
```

## Breaking Changes

1. **No longer standalone scripts** - Functions must be imported and called
2. **Different output format** - Returns dictionaries/DataFrames instead of writing files directly
3. **Explicit parameters** - All parameters must be specified (no hardcoded defaults in scripts)
4. **Error handling** - Functions return NaN for invalid inputs instead of skipping

## Migration Checklist

- [ ] Replace standalone script execution with function calls
- [ ] Update imports to use `src.volatility.volatility_processor`
- [ ] Update volatility calculation calls to use new functions
- [ ] Update ATR calculation calls
- [ ] Update regime classification logic
- [ ] Test with real data to ensure results match
- [ ] Update any downstream consumers of volatility data

## Files Requiring Updates

Run this command to find files that may need migration:

```bash
# Find references to old volatility scripts
grep -r "volatility_engine.py" --include="*.py"
grep -r "options_volatility.py" --include="*.py"
grep -r "data/processed/volatility_state.parquet" --include="*.py"
```

## Support

For questions or issues with migration, refer to:
- Volatility processor: `src/volatility/volatility_processor.py`
- State engine: `src/volatility/state_engine.py`
- Design document: `.kiro/specs/unified-volatility-engine/design.md`
