# Intelligence Engine Migration Guide

## Overview

The intelligence engines have been consolidated into a single unified implementation:
- **Old**: `src/intelligence/unified_intelligence_engine.py` + `src/cohesion/intelligence_engine.py`
- **New**: `src/volatility/intelligence_engine.py`

## What Changed

### Consolidated Features

The new `UnifiedIntelligenceEngine` combines:

1. **From unified_intelligence_engine.py**:
   - Lazy loading of intelligence components
   - Execution tracking and logging
   - Intelligence orchestration
   - State persistence

2. **From cohesion/intelligence_engine.py**:
   - Regime consistency enforcement (Property 17: I1)
   - Signal decay validation (Property 18: I2)
   - Intelligence state consistency (Property 19: I3)
   - Correctness laws and validation

### Key Improvements

- Single source of truth for intelligence state
- Unified regime detection with correctness laws
- Integrated signal tracking with decay enforcement
- Consistent API across all intelligence operations
- Better state management and persistence

## Migration Steps

### 1. Update Imports

**Old imports**:
```python
from intelligence.unified_intelligence_engine import UnifiedIntelligenceEngine
from src.cohesion.intelligence_engine import IntelligenceEngine
```

**New imports**:
```python
from src.volatility.intelligence_engine import UnifiedIntelligenceEngine
from src.volatility import UnifiedIntelligenceEngine  # Alternative
```

### 2. Update Initialization

**Old (unified_intelligence_engine.py)**:
```python
engine = UnifiedIntelligenceEngine()
intelligence_result = engine.generate_unified_intelligence()
```

**Old (cohesion/intelligence_engine.py)**:
```python
engine = IntelligenceEngine(state_manager)
result = engine.update_market_regime(market_data, as_of)
```

**New (unified)**:
```python
engine = UnifiedIntelligenceEngine(state_manager=None)  # Optional state manager
engine.initialize()

# Update regime
result = engine.update_market_regime(market_data, as_of)

# Get allocations
allocations = engine.get_strategy_allocations()

# Get state
state = engine.get_intelligence_state()
```

### 3. API Mapping

| Old Method (unified_intelligence_engine) | New Method |
|------------------------------------------|------------|
| `generate_unified_intelligence()` | `update_market_regime()` + `get_intelligence_state()` |
| `generate_market_intelligence()` | `update_market_regime()` |
| `load_latest_intelligence()` | `load_intelligence_state()` |
| `get_intelligence_status()` | `get_health_status()` |

| Old Method (cohesion/intelligence_engine) | New Method |
|-------------------------------------------|------------|
| `update_market_regime()` | `update_market_regime()` (same) |
| `get_strategy_allocations()` | `get_strategy_allocations()` (same) |
| `validate_signal_consistency()` | `validate_signal_consistency()` (same) |
| `detect_overfitting()` | `detect_overfitting()` (same) |
| `update_signal_strength()` | `update_signal_strength()` (same) |
| `get_intelligence_state()` | `get_intelligence_state()` (same) |
| `get_regime_history()` | `get_regime_history()` (same) |

### 4. Regime Enum Changes

The new engine supports all regime types from both old implementations:

```python
from src.volatility.intelligence_engine import MarketRegime

# All supported regimes:
MarketRegime.NORMAL
MarketRegime.CRISIS
MarketRegime.RECOVERY
MarketRegime.BUBBLE
MarketRegime.BEAR_MARKET
MarketRegime.BULL_MARKET
MarketRegime.LOW_VOL
MarketRegime.HIGH_VOL
MarketRegime.TRANSITION
```

### 5. State Management

**Old (cohesion)**:
```python
engine = IntelligenceEngine(state_manager)
# State manager integration was required
```

**New**:
```python
engine = UnifiedIntelligenceEngine(state_manager=None)  # Optional
# Works standalone or with state manager
```

### 6. Correctness Properties

The new engine implements all correctness properties:

- **Property 17 (I1)**: Regime Consistency - Strategy allocations adapt to regime
- **Property 18 (I2)**: Signal Decay Enforcement - Signals lose power over time
- **Property 19 (I3)**: Intelligence State Consistency - State remains valid

These are automatically enforced through validation methods.

## Example Migration

### Before (using both old engines)

```python
# From unified_intelligence_engine.py
from intelligence.unified_intelligence_engine import UnifiedIntelligenceEngine

engine1 = UnifiedIntelligenceEngine()
result = engine1.generate_unified_intelligence()
market_intel = result['market_intelligence']

# From cohesion/intelligence_engine.py
from src.cohesion.intelligence_engine import IntelligenceEngine

engine2 = IntelligenceEngine(state_manager)
regime_result = engine2.update_market_regime(market_data, datetime.now())
allocations = engine2.get_strategy_allocations(regime_result)
```

### After (using new unified engine)

```python
from src.volatility import UnifiedIntelligenceEngine

# Single engine for all intelligence operations
engine = UnifiedIntelligenceEngine(state_manager=None)
engine.initialize()

# Update regime
regime_result = engine.update_market_regime(market_data, datetime.now())

# Get allocations
allocations = engine.get_strategy_allocations()

# Get complete state
state = engine.get_intelligence_state()

# Validate signals
validation = engine.validate_signal_consistency()

# Get health status
health = engine.get_health_status()
```

## Breaking Changes

1. **Lazy loading removed**: The new engine doesn't lazy-load external components (market_brain, intelligence_stack, etc.). These should be integrated separately if needed.

2. **Execution log format**: The execution log structure is simplified. Old logs may not be compatible.

3. **State serialization**: State format has changed. Old saved states need to be regenerated.

## Benefits

1. **Single source of truth**: One engine for all intelligence operations
2. **Correctness laws**: Built-in validation and consistency checks
3. **Better testing**: Unified API makes testing easier
4. **Cleaner architecture**: No duplicate code or conflicting implementations
5. **State management**: Improved state persistence and recovery

## Testing

Test the new engine:

```python
from src.volatility import UnifiedIntelligenceEngine
import pandas as pd
import numpy as np

# Create engine
engine = UnifiedIntelligenceEngine()
engine.initialize()

# Test with sample data
sample_data = pd.DataFrame({
    'returns': np.random.randn(100) * 0.01,
    'vix': [20.0] * 100
})

# Update regime
result = engine.update_market_regime(sample_data)
print(f"Regime: {result['market_regime']}")

# Get allocations
allocations = engine.get_strategy_allocations()
print(f"Allocations: {allocations}")

# Check health
health = engine.get_health_status()
print(f"Health: {health['message']}")
```

## Support

For questions or issues with migration, refer to:
- New implementation: `src/volatility/intelligence_engine.py`
- Design document: `.kiro/specs/unified-volatility-engine/design.md`
- Requirements: `.kiro/specs/unified-volatility-engine/requirements.md`
