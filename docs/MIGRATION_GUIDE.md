# Migration Guide - Unified Volatility Engine

## Overview

This guide helps you migrate from the old Northstar v3 architecture to the new Unified Volatility Engine. The migration consolidates duplicate components, establishes clear module boundaries, and provides a unified interface for all volatility trading operations.

---

## Architecture Changes

### Old Architecture (Northstar v3)

```
Multiple scattered components:
- src/cohesion/unified_state_manager.py
- src/state/unified_state_manager.py
- src/processing/risk_engine.py
- src/cohesion/risk_engine.py
- src/risk/unified_risk_coordinator.py
- src/processing/market_regime.py
- src/processing/options_regime.py
- src/options/regime_detector.py
- src/intelligence/regime_aware_specialists.py
- Multiple dashboard implementations
- Multiple volatility processors
- Multiple intelligence engines
```

### New Architecture (Unified Engine)

```
Consolidated components:
- src/volatility/state_engine.py (single state manager)
- src/volatility/risk_authority.py (single risk engine)
- src/volatility/regime_detector.py (single regime detector)
- src/volatility/unified_engine.py (main orchestrator)
- All deprecated components archived in archive/deprecated/
```

---

## Component Migration Map

### State Management

| Old Component | New Component | Status |
|---------------|---------------|--------|
| `src/cohesion/unified_state_manager.py` | `src/volatility/state_engine.py` | Archived |
| `src/state/unified_state_manager.py` | `src/volatility/state_engine.py` | Archived |
| `src/core/*` (state-related) | `src/volatility/state_engine.py` | Archived |

**Migration Steps**:

1. Replace old imports:
```python
# OLD
from cohesion.unified_state_manager import UnifiedStateManager
from state.unified_state_manager import StateManager

# NEW
from volatility.state_engine import VolatilityStateEngine, VolatilityState
```

2. Update initialization:
```python
# OLD
state_manager = UnifiedStateManager()

# NEW
state_engine = VolatilityStateEngine()
```

3. Update method calls:
```python
# OLD
state_manager.update_state(data)
state = state_manager.get_current_state()

# NEW
state_engine.update_iv_surface(underlying, surface)
state_engine.update_regime(regime, probabilities)
state = state_engine.get_state()
```

---

### Risk Management

| Old Component | New Component | Status |
|---------------|---------------|--------|
| `src/processing/risk_engine.py` | `src/volatility/risk_authority.py` | Archived |
| `src/cohesion/risk_engine.py` | `src/volatility/risk_authority.py` | Archived |
| `src/risk/unified_risk_coordinator.py` | `src/volatility/risk_authority.py` | Archived |

**Migration Steps**:

1. Replace old imports:
```python
# OLD
from processing.risk_engine import RiskEngine
from cohesion.risk_engine import RiskEngine
from risk.unified_risk_coordinator import UnifiedRiskCoordinator

# NEW
from volatility.risk_authority import UnifiedRiskAuthority
```

2. Update initialization:
```python
# OLD
risk_engine = RiskEngine(limits=limits)

# NEW
risk_authority = UnifiedRiskAuthority(
    position_limits=position_limits,
    greeks_limits=greeks_limits,
    concentration_limits=concentration_limits,
    margin_buffer=margin_buffer
)
```

3. Update method calls:
```python
# OLD
approved = risk_engine.validate(trade)
risk_engine.check_limits(portfolio)

# NEW
result = risk_authority.validate_trade(strategy, current_state)
if result.approved:
    # proceed
else:
    # handle rejection: result.rejection_reason, result.violations
```

---

### Regime Detection

| Old Component | New Component | Status |
|---------------|---------------|--------|
| `src/processing/market_regime.py` | `src/volatility/regime_detector.py` | Archived |
| `src/processing/options_regime.py` | `src/volatility/regime_detector.py` | Archived |
| `src/options/regime_detector.py` | `src/volatility/regime_detector.py` | Archived |
| `src/intelligence/regime_aware_specialists.py` | `src/volatility/regime_detector.py` | Archived |

**Migration Steps**:

1. Replace old imports:
```python
# OLD
from processing.market_regime import MarketRegimeDetector
from processing.options_regime import OptionsRegimeDetector
from options.regime_detector import RegimeDetector

# NEW
from volatility.regime_detector import RegimeDetector
```

2. Update initialization:
```python
# OLD
regime_detector = MarketRegimeDetector()

# NEW
regime_detector = RegimeDetector()
```

3. Update method calls:
```python
# OLD
regime = regime_detector.detect(vix, vol)

# NEW
regime = regime_detector.detect_regime(
    vix=vix,
    realized_vol=realized_vol,
    correlation=correlation
)
# Returns: regime.current, regime.probabilities, regime.previous
```

---

### Volatility Processing

| Old Component | New Component | Status |
|---------------|---------------|--------|
| `src/processing/volatility_engine.py` | `src/volatility/iv_surface.py` | Archived |
| `src/processing/options_volatility.py` | `src/volatility/iv_surface.py` | Archived |

**Migration Steps**:

1. Replace old imports:
```python
# OLD
from processing.volatility_engine import VolatilityEngine
from processing.options_volatility import OptionsVolatility

# NEW
from volatility.iv_surface import IVSurface
from volatility.volatility_processor import VolatilityProcessor
```

2. Update IV surface fitting:
```python
# OLD
vol_engine = VolatilityEngine()
surface = vol_engine.fit_surface(strikes, expiries, ivs)

# NEW
surface = IVSurface(underlying="SPY")
surface.fit(strikes, expiries, ivs, spot)
iv = surface.get_iv(strike, expiry)
```

---

### Intelligence Engine

| Old Component | New Component | Status |
|---------------|---------------|--------|
| `src/intelligence/unified_intelligence_engine.py` | `src/volatility/intelligence_engine.py` | Archived |
| `src/cohesion/intelligence_engine.py` | `src/volatility/intelligence_engine.py` | Archived |

**Migration Steps**:

1. Replace old imports:
```python
# OLD
from intelligence.unified_intelligence_engine import UnifiedIntelligenceEngine
from cohesion.intelligence_engine import IntelligenceEngine

# NEW
from volatility.intelligence_engine import IntelligenceEngine
```

2. Update initialization and usage:
```python
# OLD
intel_engine = UnifiedIntelligenceEngine()
insights = intel_engine.analyze(data)

# NEW
intel_engine = IntelligenceEngine(state_engine=state_engine)
insights = intel_engine.generate_insights(state)
```

---

### Dashboard

| Old Component | New Component | Status |
|---------------|---------------|--------|
| `src/dashboard/*` (multiple) | `dashboard/volatility_dashboard.py` | Archived |

**Migration Steps**:

1. Use new unified dashboard:
```bash
# OLD
streamlit run src/dashboard/options_dashboard.py

# NEW
streamlit run dashboard/volatility_dashboard.py
```

2. Dashboard now consumes `VolatilityState` directly:
```python
# In dashboard code
from volatility.state_engine import VolatilityStateEngine

state_engine = VolatilityStateEngine()
state = state_engine.get_state()

# Display Greeks
st.metric("Delta", state.portfolio_greeks.delta)
st.metric("Gamma", state.portfolio_greeks.gamma)

# Display regime
st.write(f"Current Regime: {state.regime}")
```

---

## New Components (No Old Equivalent)

These are entirely new components in the Unified Engine:

### StrategyGenerator
```python
from volatility.strategy_generator import StrategyGenerator, TargetGreeks

strategy_gen = StrategyGenerator(state_engine=state_engine)
strategies = strategy_gen.generate_strategies(
    target_greeks=TargetGreeks(delta=0, gamma=100, vega=500),
    underlying="SPY"
)
```

### GreeksAggregator
```python
from volatility.greeks_aggregator import GreeksAggregator

greeks_agg = GreeksAggregator()
portfolio_greeks = greeks_agg.compute_portfolio_greeks(positions, state)
```

### DispersionModule
```python
from volatility.dispersion_module import DispersionModule

dispersion = DispersionModule(state_engine=state_engine)
opportunities = dispersion.identify_opportunities(index, constituents, weights)
```

### GammaScalper
```python
from volatility.gamma_scalper import GammaScalper

gamma_scalper = GammaScalper(state_engine=state_engine)
opportunities = gamma_scalper.identify_opportunities(positions, state)
```

### CapitalAllocator
```python
from volatility.capital_allocator import CapitalAllocator

allocator = CapitalAllocator()
allocations = allocator.allocate_capital(total_capital, regime, performance_history)
```

### MonteCarloEngine
```python
from volatility.monte_carlo_engine import MonteCarloEngine

mc_engine = MonteCarloEngine(n_workers=4)
paths = mc_engine.simulate_paths(n_paths, n_steps, initial_prices, correlations)
risk_metrics = mc_engine.compute_risk_metrics(pnl_distribution)
```

### ExecutionInterface
```python
from volatility.execution_interface import ExecutionInterface

execution = ExecutionInterface(venues=["CBOE", "ISE"])
orders = execution.generate_orders(strategy, execution_params)
order_id = execution.submit_order(orders[0])
```

### PerformanceMonitor
```python
from volatility.performance_monitor import PerformanceMonitor

perf_monitor = PerformanceMonitor()
perf_monitor.update_pnl(positions, state)
stats = perf_monitor.compute_performance_stats(returns, regime)
```

### UnifiedVolatilityEngine
```python
from volatility.unified_engine import UnifiedVolatilityEngine

# Main orchestrator - coordinates all components
engine = UnifiedVolatilityEngine(
    state_engine=state_engine,
    strategy_generator=strategy_gen,
    greeks_aggregator=greeks_agg,
    risk_authority=risk_authority,
    # ... all other components
)

result = engine.run_trading_cycle()
```

---

## Configuration Migration

### Old Configuration

Multiple scattered config files:
- `config/risk_limits.yaml`
- `config/position_limits.yaml`
- `config/execution_params.yaml`
- etc.

### New Configuration

Single unified config file: `config/production.yaml`

```yaml
# All configuration in one place
position_limits:
  per_underlying: 100
  total: 500

greeks_limits:
  delta: 1000
  gamma: 500
  vega: 10000
  theta: -500

risk_thresholds:
  var_95: 50000
  var_99: 100000
  cvar_95: 75000
  max_drawdown: 0.15

regime_adjustments:
  crisis:
    position_limits_multiplier: 0.5
    short_vol_allowed: false
  high_vol:
    position_limits_multiplier: 0.75
  low_vol:
    position_limits_multiplier: 1.0

execution:
  default_order_type: "LIMIT"
  preferred_venues: ["CBOE", "ISE"]

monitoring:
  pnl_update_frequency: 60
  greeks_update_frequency: 30

persistence:
  snapshot_frequency: 300
  snapshot_directory: "snapshots/"
```

**Migration Steps**:

1. Consolidate old config files into new format
2. Validate new config:
   ```bash
   python scripts/validate_config.py config/production.yaml
   ```
3. Test in staging before production

---

## Data Migration

### State Snapshots

Old state snapshots are incompatible with new format.

**Migration Steps**:

1. Export old state to JSON:
   ```bash
   python scripts/export_old_state.py --output old_state.json
   ```

2. Convert to new format:
   ```bash
   python scripts/convert_state_format.py \
     --input old_state.json \
     --output new_state.json
   ```

3. Validate new state:
   ```bash
   python scripts/validate_state.py new_state.json
   ```

4. Load into new system:
   ```bash
   python scripts/load_state.py new_state.json
   ```

---

## Testing Migration

### Old Tests

Tests scattered across multiple directories:
- `tests/test_risk_engine.py`
- `tests/test_state_manager.py`
- `tests/cohesion/test_*.py`
- etc.

### New Tests

Organized by component and type:
- `tests/test_state_engine.py` - Unit tests
- `tests/test_risk_authority.py` - Unit tests
- `tests/test_*_properties.py` - Property-based tests
- `tests/test_*_integration.py` - Integration tests

**Migration Steps**:

1. Review old tests for coverage
2. Port relevant test cases to new format
3. Add property-based tests (new requirement)
4. Run full test suite:
   ```bash
   pytest tests/ -v
   ```

---

## Deployment Migration

### Step-by-Step Migration Plan

#### Phase 1: Preparation (1 week)

1. **Backup everything**:
   ```bash
   python scripts/backup_system.py --output backup_$(date +%Y%m%d)
   ```

2. **Set up staging environment**:
   - Clone production
   - Install new system
   - Test thoroughly

3. **Train operators**:
   - Review new documentation
   - Practice emergency procedures
   - Run drills in staging

#### Phase 2: Parallel Run (2 weeks)

1. **Run both systems side-by-side**:
   - Old system in production
   - New system in shadow mode (no real trades)

2. **Compare results**:
   ```bash
   python scripts/compare_systems.py \
     --old-results old_results.csv \
     --new-results new_results.csv
   ```

3. **Validate**:
   - Strategy generation matches
   - Risk checks consistent
   - Performance similar

#### Phase 3: Cutover (1 day)

1. **Pre-cutover checklist**:
   - [ ] All tests passing
   - [ ] Configuration validated
   - [ ] Operators trained
   - [ ] Backups complete
   - [ ] Rollback plan ready

2. **Cutover procedure**:
   ```bash
   # Stop old system
   python old_system/scripts/shutdown.py
   
   # Export final state
   python old_system/scripts/export_state.py --output final_state.json
   
   # Convert state
   python scripts/convert_state_format.py \
     --input final_state.json \
     --output new_state.json
   
   # Start new system
   python scripts/start_engine.py \
     --config config/production.yaml \
     --state new_state.json
   ```

3. **Post-cutover validation**:
   - Verify all positions loaded
   - Check Greeks match
   - Confirm risk limits active
   - Test order submission

#### Phase 4: Monitoring (1 week)

1. **Intensive monitoring**:
   - Check dashboard every 15 minutes
   - Review all trades
   - Validate P&L
   - Monitor for errors

2. **Daily review**:
   - Performance vs old system
   - Any issues encountered
   - Operator feedback

3. **Adjustments**:
   - Fine-tune parameters
   - Fix any issues
   - Update documentation

#### Phase 5: Stabilization (2 weeks)

1. **Reduce monitoring intensity**
2. **Collect feedback**
3. **Optimize performance**
4. **Archive old system**

---

## Rollback Plan

If migration fails, rollback procedure:

1. **Stop new system**:
   ```bash
   python scripts/emergency_halt.py
   python scripts/shutdown_engine.py
   ```

2. **Export current state**:
   ```bash
   python scripts/save_state.py snapshots/rollback_state.json
   ```

3. **Restart old system**:
   ```bash
   cd old_system
   python scripts/start_system.py
   ```

4. **Manually reconcile positions** if needed

5. **Document what went wrong**

6. **Fix issues before retry**

---

## Common Migration Issues

### Issue 1: Import Errors

**Symptom**: `ModuleNotFoundError: No module named 'cohesion'`

**Solution**: Update all imports to new paths
```python
# OLD
from cohesion.unified_state_manager import UnifiedStateManager

# NEW
from volatility.state_engine import VolatilityStateEngine
```

---

### Issue 2: Method Not Found

**Symptom**: `AttributeError: 'VolatilityStateEngine' object has no attribute 'update_state'`

**Solution**: Use new method names
```python
# OLD
state_engine.update_state(data)

# NEW
state_engine.update_iv_surface(underlying, surface)
state_engine.update_regime(regime, probabilities)
```

---

### Issue 3: Configuration Format

**Symptom**: `ValidationError: Invalid configuration format`

**Solution**: Convert to new YAML format (see Configuration Migration section)

---

### Issue 4: State Incompatibility

**Symptom**: `StateValidationError: Cannot load state`

**Solution**: Use state conversion script
```bash
python scripts/convert_state_format.py --input old.json --output new.json
```

---

### Issue 5: Test Failures

**Symptom**: Old tests fail with new system

**Solution**: Update tests to use new interfaces (see Testing Migration section)

---

## Deprecated Components

These components are archived and should not be used:

| Component | Location | Replacement |
|-----------|----------|-------------|
| UnifiedStateManager | `archive/deprecated/state_managers/` | VolatilityStateEngine |
| RiskEngine (old) | `archive/deprecated/risk/` | UnifiedRiskAuthority |
| MarketRegimeDetector | `archive/deprecated/regime/` | RegimeDetector |
| VolatilityEngine (old) | `archive/deprecated/volatility/` | IVSurface |
| IntelligenceEngine (old) | `archive/deprecated/intelligence/` | IntelligenceEngine (new) |
| Old dashboards | `archive/deprecated/dashboard/` | volatility_dashboard.py |

**Do not delete archived components** - they are preserved for reference and potential data recovery.

---

## Support During Migration

### Resources

- **Documentation**: `docs/` directory
- **Examples**: `examples/` directory
- **Scripts**: `scripts/` directory
- **Tests**: `tests/` directory

### Getting Help

1. **Check documentation first**
2. **Review examples**
3. **Search archived components** for reference
4. **Contact**:
   - Technical lead: [EMAIL]
   - Migration support: [EMAIL]

---

## Post-Migration Checklist

After migration is complete:

- [ ] All tests passing
- [ ] All positions migrated correctly
- [ ] Greeks match expected values
- [ ] Risk limits active and correct
- [ ] Configuration validated
- [ ] Operators trained
- [ ] Documentation updated
- [ ] Emergency procedures tested
- [ ] Performance meets targets
- [ ] Old system archived
- [ ] Migration documented

---

## Timeline Summary

| Phase | Duration | Activities |
|-------|----------|------------|
| Preparation | 1 week | Backup, staging setup, training |
| Parallel Run | 2 weeks | Shadow mode, validation |
| Cutover | 1 day | Switch to new system |
| Monitoring | 1 week | Intensive monitoring |
| Stabilization | 2 weeks | Optimization, feedback |
| **Total** | **5 weeks** | |

---

## Success Criteria

Migration is successful when:

1. All positions migrated correctly
2. All tests passing
3. Performance matches or exceeds old system
4. No critical errors for 1 week
5. Operators comfortable with new system
6. Documentation complete
7. Old system can be archived

---

## Lessons Learned

Document lessons learned during migration:

1. What went well?
2. What was challenging?
3. What would you do differently?
4. What improvements are needed?

This will help future migrations and system updates.
