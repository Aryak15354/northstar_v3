# Regime Detection Migration Guide

## Overview

All regime detection components have been consolidated into a single authoritative implementation:
**`src/volatility/regime_detector.py`**

This guide documents the migration from the old implementations to the unified regime detector.

## Archived Components

The following regime detection implementations have been archived:

1. **`market_regime_v1.py`** (from `src/processing/market_regime.py`)
   - Market breadth and participation analysis
   - Correlation and volatility metrics
   - Risk-on score calculation

2. **`regime_detector_v1_options.py`** (from `src/options/regime_detector.py`)
   - IV percentile rank calculation
   - IV trend analysis (5d vs 20d MA)
   - Skew calculation
   - Vol-of-vol monitoring

3. **`options_regime_v1.py`** (from `src/processing/options_regime.py`)
   - Options-specific regime classification
   - Simple rule-based regime detection

4. **`regime_aware_specialists_v1.py`** (from `src/intelligence/regime_aware_specialists.py`)
   - Macro regime detection
   - Regime-aware signal specialists
   - Regime transition probabilities

## New Unified API

### Import Changes

**Old:**
```python
# Multiple imports from different modules
from src.processing.market_regime import build_market_regime
from src.options.regime_detector import RegimeDetector, Regime
from src.intelligence.regime_aware_specialists import RegimeAwareSpecialists
```

**New:**
```python
# Single unified import
from src.volatility.regime_detector import (
    RegimeDetector,
    VolatilityRegime,
    RegimeState,
    RegimeMetrics
)
```

### Regime Types

**Old regime types (varied across implementations):**
- `market_regime.py`: "Bull", "Bear", "Panic", "Fragile", "Neutral"
- `regime_detector.py`: LOW_VOL_SELL, HIGH_VOL_SELL, RISING_VOL_BUY, NEUTRAL, CRASH_HEDGE
- `regime_aware_specialists.py`: EXPANSION, RECESSION, RECOVERY, SLOWDOWN, CRISIS, NEUTRAL

**New unified regime types:**
```python
class VolatilityRegime(Enum):
    LOW_VOL = "low_vol"           # IV rank < 30%, stable - premium selling
    HIGH_VOL = "high_vol"         # IV rank > 70%, elevated - premium selling
    CRISIS = "crisis"             # IV rank > 80% + vol-of-vol - defensive only
    TRANSITION = "transition"     # Regime change - reduce exposure
```

### Basic Usage

**Old (market_regime.py):**
```python
import pandas as pd
from src.processing.market_regime import build_market_regime

prices = pd.read_parquet("data/processed/prices.parquet")
regime_df = build_market_regime(prices)
current_regime = regime_df.iloc[-1]['market_regime']  # "Bull", "Bear", etc.
```

**New:**
```python
import pandas as pd
from src.volatility.regime_detector import RegimeDetector

# Initialize detector
detector = RegimeDetector(
    iv_rank_lookback=252,
    vol_of_vol_threshold=1.5,
    persistence_days=3
)

# Prepare inputs
market_data = pd.read_parquet("data/processed/market_regime.parquet")
iv_history = pd.Series([...])  # Historical IV data

# Detect regime
state = detector.detect_regime(
    market_data=market_data,
    iv_history=iv_history
)

# Access regime and metrics
print(f"Regime: {state.regime.value}")
print(f"Confidence: {state.confidence:.2f}")
print(f"IV Rank: {state.metrics.iv_rank:.2%}")
```

**Old (regime_detector.py):**
```python
from src.options.regime_detector import RegimeDetector
from src.options.config_loader import get_config

config = get_config()
detector = RegimeDetector(config.regime_detection)

state = detector.detect_regime(
    option_chain=option_chain,
    iv_history=iv_history,
    underlying_regime="NORMAL"
)

if state.regime == Regime.HIGH_VOL_SELL:
    # Sell premium
    pass
```

**New:**
```python
from src.volatility.regime_detector import RegimeDetector, VolatilityRegime

detector = RegimeDetector()

state = detector.detect_regime(
    market_data=market_data,
    iv_history=iv_history,
    option_chain=option_chain  # Optional
)

if state.regime == VolatilityRegime.HIGH_VOL:
    # Sell premium
    pass
```

## Feature Mapping

### Market Metrics (from market_regime.py)

**Old:**
```python
regime_df = build_market_regime(prices)
breadth = regime_df.iloc[-1]['breadth']
participation = regime_df.iloc[-1]['participation']
risk_on_score = regime_df.iloc[-1]['risk_on_score']
```

**New:**
```python
state = detector.detect_regime(market_data, iv_history)
breadth = state.metrics.breadth
participation = state.metrics.participation
risk_on_score = state.metrics.risk_on_score
```

### IV Metrics (from regime_detector.py)

**Old:**
```python
iv_rank = detector.calculate_iv_rank(current_iv, iv_history)
skew = detector.calculate_skew(option_chain)
vol_of_vol = detector.check_vol_of_vol(iv_history)
```

**New:**
```python
state = detector.detect_regime(market_data, iv_history, option_chain)
iv_rank = state.metrics.iv_rank
skew = state.metrics.skew
vol_of_vol = state.metrics.vol_of_vol_elevated
```

### Regime Persistence (from regime_detector.py)

**Old:**
```python
persistent = detector.check_regime_persistence(regime)
days_in_regime = detector._get_days_in_regime(regime)
```

**New:**
```python
state = detector.detect_regime(market_data, iv_history)
persistent = detector.check_regime_persistence(state.regime)
days_in_regime = state.days_in_regime
```

### Tradeable Regime Check (NEW)

**New feature:**
```python
# Check if regime is suitable for trading
# Requires: confidence >= 0.6, persistence >= 3 days, not CRISIS
tradeable = detector.is_tradeable_regime(state)

if tradeable:
    # Execute trades
    pass
```

## System Laws

The unified regime detector enforces these system laws:

1. **R1: Regime Persistence** - Regime changes require 3+ days persistence (avoid whipsaws)
2. **R2: CRISIS Priority** - CRISIS regime has absolute priority (safety first)
3. **R3: Vol-of-Vol Protection** - Vol-of-vol elevation blocks premium selling (protect capital)
4. **R4: Confidence Threshold** - Regime confidence must exceed 0.6 for trading (quality threshold)

## Configuration

**Old (regime_detector.py):**
```python
from src.options.config_loader import get_config

config = get_config()
detector = RegimeDetector(config.regime_detection)
```

**New:**
```python
detector = RegimeDetector(
    iv_rank_lookback=252,        # Days for IV percentile rank
    vol_of_vol_threshold=1.5,    # Threshold for vol-of-vol elevation
    persistence_days=3,           # Days required for regime confirmation
    confidence_threshold=0.6      # Minimum confidence for trading
)
```

## Regime State Structure

The new `RegimeState` provides comprehensive regime context:

```python
@dataclass
class RegimeState:
    regime: VolatilityRegime              # Current regime
    metrics: RegimeMetrics                # All detection metrics
    timestamp: datetime                   # Detection timestamp
    confidence: float                     # Overall confidence (0-1)
    days_in_regime: int                  # Consecutive days in regime
    transition_probability: Dict          # Transition probabilities
    reason: str                          # Human-readable reason
```

## Transition Probabilities

**Old (regime_aware_specialists.py):**
```python
regime_context = regime_detector.detect_regime(current_time)
transition_probs = regime_context.transition_probability
```

**New:**
```python
state = detector.detect_regime(market_data, iv_history)
transition_probs = state.transition_probability

for regime, prob in transition_probs.items():
    print(f"{regime.value}: {prob:.2%}")
```

## Breaking Changes

1. **Regime enum names changed** - Update all regime comparisons
2. **No more config file** - Pass parameters directly to constructor
3. **Unified input format** - Requires market_data DataFrame and iv_history Series
4. **No underlying_regime parameter** - Market regime integrated into metrics
5. **Regime-aware specialists removed** - Use unified regime detector only

## Migration Checklist

- [ ] Update imports to use `src.volatility.regime_detector`
- [ ] Update regime enum references (e.g., `Regime.HIGH_VOL_SELL` → `VolatilityRegime.HIGH_VOL`)
- [ ] Update regime detection calls to use new API
- [ ] Remove config file dependencies
- [ ] Update regime persistence checks
- [ ] Add tradeable regime checks where appropriate
- [ ] Update tests to use new regime types
- [ ] Remove references to archived modules

## Files Requiring Updates

Run this command to find files that need migration:

```bash
# Find imports of old regime modules
grep -r "from src.processing.market_regime" --include="*.py"
grep -r "from src.options.regime_detector" --include="*.py"
grep -r "from src.intelligence.regime_aware_specialists" --include="*.py"
grep -r "from src.processing.options_regime" --include="*.py"
```

## Support

For questions or issues with migration, refer to:
- Unified regime detector: `src/volatility/regime_detector.py`
- Design document: `.kiro/specs/unified-volatility-engine/design.md`
- Requirements: `.kiro/specs/unified-volatility-engine/requirements.md`
