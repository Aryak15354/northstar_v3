# Regime Detection Import Updates Required

## Active Files Requiring Updates

The following active files import old regime detection modules and need to be updated:

### Options Module Files

1. **`src/options/trade_eligibility_validator.py`**
   - Imports: `from src.options.regime_detector import Regime, RegimeState`
   - Update to: `from src.volatility.regime_detector import VolatilityRegime, RegimeState`
   - Changes: Replace `Regime` enum with `VolatilityRegime`

2. **`src/options/backtest_simulation_engine.py`**
   - Imports: `from src.options.regime_detector import RegimeDetector, Regime`
   - Update to: `from src.volatility.regime_detector import RegimeDetector, VolatilityRegime`
   - Changes: Replace `Regime` enum with `VolatilityRegime`

3. **`src/options/system_hygiene.py`**
   - Imports: `from src.options.regime_detector import Regime`
   - Update to: `from src.volatility.regime_detector import VolatilityRegime`
   - Changes: Replace `Regime` enum with `VolatilityRegime`

4. **`src/options/position_manager.py`**
   - Imports: `from src.options.regime_detector import Regime`
   - Update to: `from src.volatility.regime_detector import VolatilityRegime`
   - Changes: Replace `Regime` enum with `VolatilityRegime`

5. **`src/options/strategy_generator.py`**
   - Imports: `from src.options.regime_detector import Regime`
   - Update to: `from src.volatility.regime_detector import VolatilityRegime`
   - Changes: Replace `Regime` enum with `VolatilityRegime`

### Intelligence Module Files

6. **`src/intelligence/stress_testing_system.py`**
   - Imports: `from src.intelligence.regime_aware_specialists import MarketRegime, RegimeContext`
   - Update to: `from src.volatility.regime_detector import VolatilityRegime, RegimeState`
   - Changes: Replace `MarketRegime` with `VolatilityRegime`, `RegimeContext` with `RegimeState`

7. **`src/intelligence/real_time_health_monitor.py`**
   - Imports: `from src.intelligence.regime_aware_specialists import MarketRegime, RegimeContext`
   - Update to: `from src.volatility.regime_detector import VolatilityRegime, RegimeState`
   - Changes: Replace `MarketRegime` with `VolatilityRegime`, `RegimeContext` with `RegimeState`

8. **`src/intelligence/signal_health_monitor.py`**
   - Imports: `from src.intelligence.regime_aware_specialists import SpecialistSignal, RegimeContext, MarketRegime`
   - Update to: `from src.volatility.regime_detector import VolatilityRegime, RegimeState`
   - Changes: Replace `MarketRegime` with `VolatilityRegime`, `RegimeContext` with `RegimeState`
   - Note: `SpecialistSignal` is no longer available - needs refactoring

9. **`src/intelligence/economic_causality_validator.py`**
   - Imports: `from src.intelligence.regime_aware_specialists import MarketRegime, RegimeContext`
   - Update to: `from src.volatility.regime_detector import VolatilityRegime, RegimeState`
   - Changes: Replace `MarketRegime` with `VolatilityRegime`, `RegimeContext` with `RegimeState`

10. **`src/intelligence/bayesian_capital_tribunal.py`**
    - Imports: `from src.intelligence.regime_aware_specialists import SpecialistSignal, RegimeContext, MarketRegime`
    - Update to: `from src.volatility.regime_detector import VolatilityRegime, RegimeState`
    - Changes: Replace `MarketRegime` with `VolatilityRegime`, `RegimeContext` with `RegimeState`
    - Note: `SpecialistSignal` is no longer available - needs refactoring

### Validation Module Files

11. **`src/validation/crisis_validator.py`**
    - Imports: `from src.intelligence.regime_aware_specialists import MarketRegime`
    - Update to: `from src.volatility.regime_detector import VolatilityRegime`
    - Changes: Replace `MarketRegime` with `VolatilityRegime`

## Regime Enum Mapping

### Old Regime Types → New Regime Types

**From `src.options.regime_detector.Regime`:**
- `Regime.LOW_VOL_SELL` → `VolatilityRegime.LOW_VOL`
- `Regime.HIGH_VOL_SELL` → `VolatilityRegime.HIGH_VOL`
- `Regime.RISING_VOL_BUY` → `VolatilityRegime.TRANSITION` (or handle separately)
- `Regime.NEUTRAL` → `VolatilityRegime.TRANSITION`
- `Regime.CRASH_HEDGE` → `VolatilityRegime.CRISIS`

**From `src.intelligence.regime_aware_specialists.MarketRegime`:**
- `MarketRegime.EXPANSION` → `VolatilityRegime.LOW_VOL` (approximate)
- `MarketRegime.RECESSION` → `VolatilityRegime.HIGH_VOL` or `CRISIS`
- `MarketRegime.RECOVERY` → `VolatilityRegime.TRANSITION`
- `MarketRegime.SLOWDOWN` → `VolatilityRegime.TRANSITION`
- `MarketRegime.CRISIS` → `VolatilityRegime.CRISIS`
- `MarketRegime.NEUTRAL` → `VolatilityRegime.TRANSITION`

## Class/Type Mapping

- `RegimeContext` → `RegimeState`
- `RegimeMetrics` (old) → `RegimeMetrics` (new, different structure)
- `SpecialistSignal` → No longer available (removed with regime_aware_specialists)

## Breaking Changes

1. **SpecialistSignal removed**: Files using `SpecialistSignal` need refactoring
   - Affected: `signal_health_monitor.py`, `bayesian_capital_tribunal.py`
   - Solution: Remove specialist signal dependencies or create new signal types

2. **RegimeContext → RegimeState**: Different structure
   - Old: `RegimeContext(regime, confidence, regime_duration, transition_probability, macro_indicators)`
   - New: `RegimeState(regime, metrics, timestamp, confidence, days_in_regime, transition_probability, reason)`

3. **Regime detection API changed**:
   - Old: `detector.detect_regime(option_chain, iv_history, underlying_regime)`
   - New: `detector.detect_regime(market_data, iv_history, option_chain, current_time)`

## Update Priority

### High Priority (Core Trading Logic)
1. `src/options/trade_eligibility_validator.py`
2. `src/options/strategy_generator.py`
3. `src/options/position_manager.py`
4. `src/options/backtest_simulation_engine.py`

### Medium Priority (Monitoring & Validation)
5. `src/validation/crisis_validator.py`
6. `src/options/system_hygiene.py`

### Low Priority (Intelligence Layer - May Need Refactoring)
7. `src/intelligence/stress_testing_system.py`
8. `src/intelligence/real_time_health_monitor.py`
9. `src/intelligence/economic_causality_validator.py`

### Requires Refactoring (SpecialistSignal Dependencies)
10. `src/intelligence/signal_health_monitor.py`
11. `src/intelligence/bayesian_capital_tribunal.py`

## Backup Files

The following files in `backups/` directories also have old imports but are not active:
- All files in `backups/root_cleanup_archive_20260123_000918/`
- All files in `backups/pre_cleanup_20260117_013055/`

These backup files do NOT need to be updated.

## Update Commands

To update imports automatically (for simple cases):

```bash
# Update Regime → VolatilityRegime
find src -name "*.py" -type f -exec sed -i '' 's/from src\.options\.regime_detector import Regime/from src.volatility.regime_detector import VolatilityRegime/g' {} +

# Update RegimeContext → RegimeState
find src -name "*.py" -type f -exec sed -i '' 's/RegimeContext/RegimeState/g' {} +

# Update MarketRegime → VolatilityRegime
find src -name "*.py" -type f -exec sed -i '' 's/MarketRegime/VolatilityRegime/g' {} +
```

**WARNING**: These commands will make bulk changes. Review each file manually after running.

## Manual Review Required

After automated updates, manually review:
1. Enum value usage (e.g., `Regime.LOW_VOL_SELL` → `VolatilityRegime.LOW_VOL`)
2. RegimeState field access (structure changed)
3. Regime detection API calls (parameters changed)
4. Files with SpecialistSignal dependencies (need refactoring)

## Testing After Updates

After updating imports, run:
```bash
# Check for import errors
python -m py_compile src/options/*.py
python -m py_compile src/intelligence/*.py
python -m py_compile src/validation/*.py

# Run tests
pytest tests/ -v
```

## Status

- [ ] High priority files updated
- [ ] Medium priority files updated
- [ ] Low priority files updated
- [ ] Files requiring refactoring addressed
- [ ] All tests passing
- [ ] Manual review complete
