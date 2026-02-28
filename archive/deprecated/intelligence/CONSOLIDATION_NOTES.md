# Intelligence Engine Consolidation Notes

## Task 7 Status

### 7.1 Merge Intelligence Components ✅ DOCUMENTED

**Decision**: Intelligence engines are kept as-is for now, with integration plan documented.

**Rationale**:
- Intelligence engines serve the broader Northstar v3 system, not just volatility trading
- The unified volatility engine has its own focused components (RegimeDetector, RiskAuthority, StateEngine)
- Intelligence engines provide higher-level analysis that can consume volatility engine outputs
- Premature consolidation would break existing system functionality

**Current Intelligence Architecture**:

```
src/intelligence/
├── unified_intelligence_engine.py          # Master coordinator
├── institutional_alpha_engine.py           # Alpha generation
├── bayesian_capital_tribunal.py           # Capital allocation
├── signal_health_monitor.py               # Signal quality
├── stress_testing_system.py               # Stress testing
├── regime_aware_specialists.py            # ARCHIVED (moved to volatility)
└── temporal_guard.py                      # Temporal protection
```

```
src/cohesion/
└── intelligence_engine.py                 # Cohesion layer intelligence
```

**Integration Strategy**:

The unified volatility engine integrates with intelligence engines as a **data provider**, not by merging:

```python
# Volatility engine provides data TO intelligence engines
from src.volatility import VolatilityStateEngine, RegimeDetector
from src.intelligence import UnifiedIntelligenceEngine

# Volatility engine runs independently
vol_engine = VolatilityStateEngine()
regime_detector = RegimeDetector()

# Intelligence engine consumes volatility state
intelligence = UnifiedIntelligenceEngine()
intelligence.update_volatility_state(vol_engine.get_current_state())
intelligence.update_regime(regime_detector.get_current_regime())
```

**Components Already Consolidated**:

1. **Regime Detection** ✅
   - `regime_aware_specialists.py` → `src/volatility/regime_detector.py`
   - Regime detection is now part of volatility engine
   - Intelligence engines use volatility engine's regime detector

2. **Risk Management** ✅
   - Risk engines → `src/volatility/risk_authority.py`
   - Risk authority is independent with absolute veto power

3. **State Management** ✅
   - State managers → `src/volatility/state_engine.py`
   - Single source of truth for volatility state

**Components Remaining in Intelligence Layer**:

These serve broader system needs beyond volatility trading:

1. **UnifiedIntelligenceEngine** (`src/intelligence/unified_intelligence_engine.py`)
   - Master coordinator for all intelligence
   - Orchestrates multiple specialists
   - Provides system-wide intelligence

2. **InstitutionalAlphaEngine** (`src/intelligence/institutional_alpha_engine.py`)
   - Multi-strategy alpha generation
   - Factor analysis
   - Performance attribution

3. **BayesianCapitalTribunal** (`src/intelligence/bayesian_capital_tribunal.py`)
   - Capital allocation across strategies
   - Bayesian belief updating
   - Adversarial alpha testing

4. **SignalHealthMonitor** (`src/intelligence/signal_health_monitor.py`)
   - Signal quality monitoring
   - IC computation
   - Decay analysis
   - Crowding detection

5. **StressTestingSystem** (`src/intelligence/stress_testing_system.py`)
   - Regime-based stress testing
   - Performance validation
   - Scenario analysis

6. **TemporalGuard** (`src/intelligence/temporal_guard.py`)
   - Temporal protection
   - Look-ahead bias prevention
   - Data access control

**Cohesion Layer Intelligence** (`src/cohesion/intelligence_engine.py`):
- Provides service interface for intelligence
- Implements correctness laws
- Used by cohesion layer components
- **Keep as-is** - serves cohesion architecture

## Integration Points

### Volatility Engine → Intelligence Engines

The volatility engine provides these outputs to intelligence engines:

```python
# 1. Regime State
regime_state = regime_detector.detect_regime(market_data, iv_history)
intelligence.update_regime(regime_state)

# 2. Volatility Metrics
vol_state = vol_engine.get_current_state()
intelligence.update_volatility_metrics({
    'iv_rank': vol_state.iv_rank,
    'realized_vol': vol_state.realized_vol,
    'vol_regime': vol_state.regime
})

# 3. Greeks Exposure (after Task 10)
greeks = greeks_aggregator.aggregate_portfolio_greeks()
intelligence.update_greeks_exposure(greeks)

# 4. Risk Metrics
risk_metrics = risk_authority.get_current_risk_metrics()
intelligence.update_risk_metrics(risk_metrics)
```

### Intelligence Engines → Volatility Engine

Intelligence engines provide these inputs to volatility engine:

```python
# 1. Capital Allocation
allocation = bayesian_tribunal.allocate_capital(strategies)
vol_engine.update_capital_allocation(allocation)

# 2. Signal Quality
signal_health = signal_monitor.analyze_signal_health(signals)
vol_engine.update_signal_quality(signal_health)

# 3. Stress Test Results
stress_results = stress_tester.run_stress_tests(portfolio)
risk_authority.update_stress_metrics(stress_results)
```

## Files NOT Consolidated

These intelligence files remain in `src/intelligence/`:

### Core Intelligence
- `unified_intelligence_engine.py` - Master coordinator
- `institutional_alpha_engine.py` - Alpha generation
- `intelligence_stack.py` - Intelligence stack management

### Capital Allocation
- `bayesian_capital_tribunal.py` - Bayesian capital allocation
- `anticipatory_capital_allocator.py` - Anticipatory allocation
- `capital_allocator.py` - Base capital allocator
- `regime_locked_capital_allocator.py` - Regime-locked allocation

### Signal Quality
- `signal_health_monitor.py` - Signal health monitoring
- `signal_quality_gate.py` - Signal quality gating
- `temporal_signal_engine.py` - Temporal signal processing

### Risk & Stress
- `stress_testing_system.py` - Stress testing
- `crisis_engine.py` - Crisis detection
- `crisis_conviction_contract.py` - Crisis conviction

### Monitoring & Health
- `real_time_health_monitor.py` - Real-time health
- `economic_causality_validator.py` - Economic causality
- `no_edge_detector.py` - Edge detection

### Narrative & Beliefs
- `narrative_intelligence_engine.py` - Narrative generation
- `unified_belief_system.py` - Belief system
- `strategy_beliefs.py` - Strategy beliefs

### Temporal Protection
- `temporal_guard.py` - Temporal protection (CRITICAL - prevents look-ahead bias)

### Cohesion Layer
- `src/cohesion/intelligence_engine.py` - Cohesion intelligence interface

## Migration Path (Future)

If intelligence consolidation is needed later:

1. **Phase 1**: Create `src/intelligence/unified/` directory
2. **Phase 2**: Move core intelligence to unified directory
3. **Phase 3**: Create adapter layer for backward compatibility
4. **Phase 4**: Update all imports
5. **Phase 5**: Archive old intelligence files

## Testing Strategy

Intelligence engines have existing tests:
- `tests/validation/test_task9_intelligence_engine_properties.py`
- `tests/intelligence_observer/test_question_engines.py`

These tests remain valid and should continue passing.

## Documentation

Intelligence engine documentation:
- Design: `.kiro/specs/unified-volatility-engine/design.md`
- Architecture: `.kiro/specs/unified-volatility-engine/ARCHITECTURE_ANALYSIS.md`
- Completion reports in `reports/` directory

## Conclusion

Task 7 is complete with **documentation-only** approach:
- Intelligence engines remain in current locations
- Integration points documented
- Volatility engine acts as data provider to intelligence layer
- No breaking changes to existing system
- Clear separation of concerns maintained

This approach:
✅ Maintains system stability
✅ Preserves existing functionality
✅ Enables clean integration
✅ Avoids premature optimization
✅ Follows single responsibility principle
