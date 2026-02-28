# State Manager Migration Guide

## Overview

The Northstar v3 system had multiple state manager implementations that have been consolidated into a single unified `VolatilityStateEngine` in `src/volatility/state_engine.py`.

**Migration Date:** 2026-02-11  
**Deprecated Implementations:**
- `src/state/unified_state_manager.py` → Read-only state manager
- `src/cohesion/unified_state_manager.py` → Capital-grade state manager

**New Implementation:**
- `src/volatility/state_engine.py` → Unified Volatility State Engine

---

## What Changed

### Architecture Changes

**Before:**
```
src/state/unified_state_manager.py (read-only)
src/cohesion/unified_state_manager.py (capital-grade)
```

**After:**
```
src/volatility/state_engine.py (unified, volatility-focused)
```

### Key Improvements

1. **Volatility-Specific State Model**
   - Dedicated `VolatilityState` dataclass with all volatility-related fields
   - IV surface integration (placeholder for IVSurface object)
   - Regime state with confidence scoring
   - Correlation matrix management
   - Portfolio Greeks snapshot
   - Event risk tracking

2. **Simplified Authority Model**
   - Reduced from complex hierarchy to 5 clear levels:
     - EMERGENCY (1) - Absolute authority
     - SYSTEM (2) - System-level
     - PORTFOLIO (3) - Portfolio decisions
     - INTELLIGENCE (4) - Signals/analysis
     - MARKET_DATA (5) - Market data updates

3. **Enhanced Validation**
   - Comprehensive state consistency checks
   - Validation status with errors and warnings
   - Automatic validation on every update

4. **Better Integration**
   - Designed for volatility trading workflows
   - Clean interfaces for IV surface, regime, Greeks
   - Event-driven subscriber model

---

## Migration Steps

### Step 1: Update Imports

**Old Code:**
```python
from src.state.unified_state_manager import UnifiedStateManager
# or
from src.cohesion.unified_state_manager import UnifiedStateManager
```

**New Code:**
```python
from src.volatility.state_engine import VolatilityStateEngine, VolatilityState
```

### Step 2: Update Initialization

**Old Code:**
```python
state_manager = UnifiedStateManager()
```

**New Code:**
```python
state_engine = VolatilityStateEngine(persistence_dir="data/volatility_state")
```

### Step 3: Update State Access

**Old Code:**
```python
# Read-only version
state_manager.update_all_state()
unified_state = state_manager.get_unified_state()
market_state = unified_state['market']
```

**New Code:**
```python
# Direct state access
state = state_engine.get_state()
vix_level = state.vix_level
regime = state.regime.regime
```

### Step 4: Update State Updates

**Old Code (Cohesion Version):**
```python
from src.cohesion.unified_state_manager import AuthorityLevel

state_manager.update_state(
    component="market",
    updates={"regime": "expansion", "risk_on": 0.75},
    authority=AuthorityLevel.INTELLIGENCE,
    reason="Market regime update"
)
```

**New Code:**
```python
from src.volatility.state_engine import AuthorityLevel, RegimeState
from datetime import timedelta

# Update regime
regime = RegimeState(
    regime='low_vol',
    confidence=0.85,
    duration=timedelta(days=5)
)
state_engine.update_regime(regime)

# Update volatility metrics
state_engine.update_volatility_metrics(
    vix_level=18.5,
    realized_vol_20d=0.15,
    vol_of_vol=1.2
)
```

### Step 5: Update Subscriptions

**Old Code:**
```python
def on_market_change(component, updates, state):
    print(f"Market state changed: {updates}")

state_manager.subscribe_to_changes("market", on_market_change)
```

**New Code:**
```python
def on_volatility_change(component, updates, state):
    print(f"Volatility state changed: {updates}")

state_engine.subscribe_to_changes("volatility", on_volatility_change)
```

---

## API Mapping

### State Access

| Old API | New API |
|---------|---------|
| `state_manager.get_unified_state()` | `state_engine.get_state()` |
| `state_manager.market_state` | `state_engine.get_state().vix_level` (direct field access) |
| `state_manager.get_component_state("market")` | `state_engine.get_state()` (single state object) |
| `state_manager.get_state_for_dashboard()` | Custom formatting from `state_engine.get_state()` |

### State Updates

| Old API | New API |
|---------|---------|
| `state_manager.update_market_state()` | `state_engine.update_volatility_metrics()` |
| `state_manager.update_all_state()` | Multiple specific update calls |
| `state_manager.update_state(component, updates, ...)` | Specific update methods |

### Persistence

| Old API | New API |
|---------|---------|
| `state_manager.save_state()` | `state_engine.persist_state()` |
| `state_manager.load_state()` | `state_engine.restore_state()` |

### Validation

| Old API | New API |
|---------|---------|
| `state_manager.validate_state_integrity()` | `state_engine.validate_state()` |
| N/A | `state_engine.get_system_health()` |

---

## Breaking Changes

### 1. State Structure

**Old:** Nested dictionary structure
```python
{
    'market': {...},
    'intelligence': {...},
    'portfolio': {...},
    'risk': {...}
}
```

**New:** Flat dataclass with typed fields
```python
VolatilityState(
    vix_level=18.5,
    regime=RegimeState(...),
    correlation_matrix=np.array(...),
    portfolio_greeks=PortfolioGreeks(...)
)
```

### 2. Authority Levels

**Old:** 5 levels (EMERGENCY, SYSTEM, PORTFOLIO, INTELLIGENCE, POSITION)

**New:** 5 levels (EMERGENCY, SYSTEM, PORTFOLIO, INTELLIGENCE, MARKET_DATA)

Change: `POSITION` → `MARKET_DATA` (more appropriate for volatility context)

### 3. Component Names

**Old:** Components were 'market', 'intelligence', 'portfolio', 'risk'

**New:** Single component 'volatility' with all volatility-related state

### 4. Update Methods

**Old:** Generic `update_state(component, updates, ...)`

**New:** Specific methods:
- `update_iv_surface()`
- `update_regime()`
- `update_correlations()`
- `update_volatility_metrics()`
- `update_portfolio_greeks()`

---

## Compatibility Layer (Temporary)

If you need temporary compatibility while migrating, you can create a wrapper:

```python
# compatibility_wrapper.py
from src.volatility.state_engine import VolatilityStateEngine

class UnifiedStateManagerCompat:
    """Temporary compatibility wrapper"""
    
    def __init__(self):
        self.engine = VolatilityStateEngine()
    
    def get_unified_state(self):
        """Old API compatibility"""
        state = self.engine.get_state()
        return {
            'timestamp': state.timestamp.isoformat(),
            'version': state.version,
            'market': {
                'vix_level': state.vix_level,
                'regime': state.regime.regime,
                'realized_vol_20d': state.realized_vol_20d,
                # ... map other fields
            },
            # ... map other components
        }
    
    def update_all_state(self):
        """Old API compatibility - does nothing"""
        # New engine updates on-demand, not batch
        return True
```

---

## Testing Your Migration

### 1. Unit Tests

Update your unit tests to use the new API:

```python
def test_state_engine():
    engine = VolatilityStateEngine()
    
    # Test volatility metrics update
    success = engine.update_volatility_metrics(vix_level=20.0)
    assert success
    
    state = engine.get_state()
    assert state.vix_level == 20.0
    
    # Test validation
    validation = engine.validate_state()
    assert validation.is_valid
```

### 2. Integration Tests

Test the complete flow:

```python
def test_integration():
    engine = VolatilityStateEngine()
    
    # Subscribe to changes
    changes = []
    def on_change(component, updates, state):
        changes.append(updates)
    
    engine.subscribe_to_changes("volatility", on_change)
    
    # Update state
    engine.update_volatility_metrics(vix_level=25.0)
    
    # Verify subscription fired
    assert len(changes) > 0
```

### 3. Regression Tests

Run your existing test suite to catch any issues:

```bash
python3 -m pytest tests/ -v
```

---

## Rollback Plan

If you need to rollback:

1. **Restore old files:**
   ```bash
   cp archive/deprecated/state_managers/unified_state_manager_v1_readonly.py src/state/unified_state_manager.py
   cp archive/deprecated/state_managers/unified_state_manager_v1_cohesion.py src/cohesion/unified_state_manager.py
   ```

2. **Revert imports:**
   ```bash
   # Use your version control system
   git checkout HEAD -- src/state/unified_state_manager.py
   git checkout HEAD -- src/cohesion/unified_state_manager.py
   ```

3. **Update imports back:**
   ```python
   from src.state.unified_state_manager import UnifiedStateManager
   ```

---

## Support

If you encounter issues during migration:

1. Check this migration guide
2. Review the new API documentation in `src/volatility/state_engine.py`
3. Look at the test examples in the `main()` function
4. Check the architecture analysis in `.kiro/specs/unified-volatility-engine/ARCHITECTURE_ANALYSIS.md`

---

## Timeline

- **Phase 1 (Week 1):** New state engine implemented
- **Phase 2 (Week 2):** Update all imports and basic usage
- **Phase 3 (Week 3):** Update advanced features (subscriptions, persistence)
- **Phase 4 (Week 4):** Remove old implementations, complete migration

---

## Deprecated Files

The following files have been archived and should no longer be used:

- `src/state/unified_state_manager.py` → `archive/deprecated/state_managers/unified_state_manager_v1_readonly.py`
- `src/cohesion/unified_state_manager.py` → `archive/deprecated/state_managers/unified_state_manager_v1_cohesion.py`

**DO NOT** import from these archived files. They are kept for reference only.

---

**Migration Status:** IN PROGRESS  
**Target Completion:** 2026-02-25  
**Contact:** Northstar Development Team
