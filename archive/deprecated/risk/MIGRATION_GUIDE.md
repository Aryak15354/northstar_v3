# Risk Components Migration Guide

## Overview

This guide documents the migration from the old risk management components to the new unified `UnifiedRiskAuthority` in `src/volatility/risk_authority.py`.

**Migration Date:** February 11, 2026

**Deprecated Components:**
- `src/risk/unified_risk_coordinator.py` → `archive/deprecated/risk/unified_risk_coordinator_v1.py`
- `src/cohesion/risk_authority.py` → `archive/deprecated/risk/risk_authority_v1_cohesion.py`
- `src/cohesion/risk_engine.py` → `archive/deprecated/risk/risk_engine_v1_cohesion.py`

**New Component:**
- `src/volatility/risk_authority.py` - Unified Risk Authority with absolute veto power

**Specialized Components (Keep Using):**
- `src/risk/emergency_brake.py` - Emergency brake system (integrate via Risk Authority)
- `src/risk/portfolio_risk_controller.py` - Dynamic exposure scaling (integrate via Risk Authority)
- `src/risk/liquidity_kill_switch.py` - Liquidity risk assessment (integrate via Risk Authority)

---

## Why Consolidate?

The old architecture had three separate risk implementations with overlapping functionality:

1. **UnifiedRiskCoordinator** - Orchestrated emergency brake and portfolio risk control
2. **RiskAuthority** - Managed risk parameters with authority hierarchy
3. **RiskEngine** - Validated risk invariants (R1-R4)

This created:
- Duplicate code and logic
- Unclear authority boundaries
- Difficult maintenance
- Inconsistent risk enforcement

The new `UnifiedRiskAuthority` consolidates all functionality into a single, authoritative component.

---

## API Migration

### 1. UnifiedRiskCoordinator → UnifiedRiskAuthority

#### Old Code:
```python
from src.risk.unified_risk_coordinator import UnifiedRiskCoordinator

coordinator = UnifiedRiskCoordinator()
success = coordinator.apply_unified_risk_management()

# Get emergency state
emergency_state = coordinator.run_emergency_brake_check()
```

#### New Code:
```python
from src.volatility.risk_authority import create_risk_authority

risk_authority = create_risk_authority()

# Validate trade
result = risk_authority.validate_trade(trade, portfolio, regime='low-vol')
if result.approved:
    # Execute trade
    pass

# Get emergency actions
actions = risk_authority.get_emergency_actions(market_conditions, portfolio)

# Get risk state
state = risk_authority.get_risk_state()
```

---

### 2. RiskAuthority (Cohesion) → UnifiedRiskAuthority

#### Old Code:
```python
from src.cohesion.risk_authority import RiskAuthority, AuthorityLevel

risk_authority = RiskAuthority(config_manager, audit_logger)
risk_params = risk_authority.get_risk_parameters()

# Update parameters
result = risk_authority.update_risk_parameters(
    updates={'max_position_size': 0.10},
    authority_level=AuthorityLevel.OPERATOR,
    set_by='operator',
    reason='Increase position limits'
)

# Emergency override
risk_authority.trigger_emergency_override(
    parameters={'max_exposure': 0.50},
    triggered_by='system',
    reason='Market crisis'
)
```

#### New Code:
```python
from src.volatility.risk_authority import create_risk_authority, AuthorityLevel

risk_authority = create_risk_authority()

# Get limits
limits = risk_authority.limits

# Update limits (modify limits object directly)
risk_authority.limits.max_position_size = 0.10

# Emergency override
risk_authority.trigger_emergency_override(
    exposure_cap=0.50,
    triggered_by='system',
    reason='Market crisis'
)
```

---

### 3. RiskEngine (Cohesion) → UnifiedRiskAuthority

#### Old Code:
```python
from src.cohesion.risk_engine import RiskEngine

risk_engine = RiskEngine(config_manager, state_manager, risk_authority)

# Validate position size
result = risk_engine.validate_position_size(symbol, size, portfolio)

# Calculate portfolio risk
risk_metrics = risk_engine.calculate_portfolio_risk(portfolio)

# Check risk limits
result = risk_engine.check_risk_limits(portfolio)

# Get emergency actions
actions = risk_engine.get_emergency_actions(market_conditions)

# Validate invariants
is_valid, error = risk_engine.validate_capital_conservation(
    previous_nav, current_nav, pnl, costs
)
```

#### New Code:
```python
from src.volatility.risk_authority import create_risk_authority

risk_authority = create_risk_authority()

# Validate trade (includes position size validation)
result = risk_authority.validate_trade(trade, portfolio, regime='low-vol')

# Get emergency actions
actions = risk_authority.get_emergency_actions(market_conditions, portfolio)

# Validate invariants
is_valid, error = risk_authority.validate_capital_conservation(
    previous_nav, current_nav, pnl, costs
)

is_valid, error = risk_authority.validate_crisis_derisking(
    crisis_start, pre_crisis_exposure, current_exposure
)

is_valid, error = risk_authority.validate_risk_of_ruin(max_drawdown)
```

---

## Feature Mapping

### UnifiedRiskCoordinator Features

| Old Feature | New Feature | Notes |
|------------|-------------|-------|
| `run_emergency_brake_check()` | `trigger_emergency_override()` | Simplified API |
| `run_portfolio_risk_control()` | `validate_trade()` | Integrated into trade validation |
| `apply_risk_authority_to_portfolio()` | `validate_trade()` | Automatic enforcement |
| `save_unified_risk_state()` | `get_risk_state()` | State retrieval |
| `log_risk_action()` | Automatic audit trail | Built-in logging |

### RiskAuthority (Cohesion) Features

| Old Feature | New Feature | Notes |
|------------|-------------|-------|
| `get_risk_parameters()` | `limits` attribute | Direct access |
| `update_risk_parameters()` | Modify `limits` directly | Simpler API |
| `validate_risk_consistency()` | Automatic validation | Built-in |
| `get_emergency_parameters()` | `trigger_emergency_override()` | Simplified |
| `trigger_emergency_override()` | `trigger_emergency_override()` | Same name, different signature |
| `get_authority_info()` | `get_risk_state()` | Consolidated |

### RiskEngine (Cohesion) Features

| Old Feature | New Feature | Notes |
|------------|-------------|-------|
| `validate_position_size()` | `validate_trade()` | Integrated |
| `calculate_portfolio_risk()` | Internal helper methods | Not exposed |
| `check_risk_limits()` | `validate_trade()` | Integrated |
| `get_emergency_actions()` | `get_emergency_actions()` | Same API |
| `validate_capital_conservation()` | `validate_capital_conservation()` | Same API |
| `validate_crisis_derisking()` | `validate_crisis_derisking()` | Same API |
| `validate_risk_of_ruin_protection()` | `validate_risk_of_ruin()` | Renamed |

---

## Key Differences

### 1. Simplified Authority Hierarchy

**Old:** Complex authority levels with configuration manager integration
```python
AuthorityLevel.EMERGENCY > OPERATOR > CONFIGURATION > SYSTEM
```

**New:** Streamlined hierarchy focused on emergency vs normal operations
```python
AuthorityLevel.EMERGENCY > OPERATOR > CONFIGURATION > SYSTEM
```

### 2. Trade Validation

**Old:** Separate validation for position size, sector exposure, Greeks
```python
result1 = risk_engine.validate_position_size(symbol, size, portfolio)
result2 = risk_engine.check_risk_limits(portfolio)
```

**New:** Unified trade validation
```python
result = risk_authority.validate_trade(trade, portfolio, regime='low-vol')
# Returns: TradeValidationResult with all violations
```

### 3. Emergency Override

**Old:** Parameter-based override
```python
risk_authority.trigger_emergency_override(
    parameters={'max_exposure': 0.50},
    triggered_by='system',
    reason='Crisis'
)
```

**New:** Exposure cap-based override
```python
risk_authority.trigger_emergency_override(
    exposure_cap=0.50,
    triggered_by='system',
    reason='Crisis'
)
```

### 4. Regime-Conditional Limits

**Old:** Manual regime handling
```python
if regime == 'crisis':
    max_exposure = 0.40
elif regime == 'high-vol':
    max_exposure = 0.60
```

**New:** Automatic regime handling
```python
result = risk_authority.validate_trade(trade, portfolio, regime='crisis')
# Automatically applies crisis limits
```

---

## Integration with Specialized Components

The new Risk Authority integrates with specialized components:

### Emergency Brake Integration

```python
from src.risk.emergency_brake import EmergencyBrakeEngine
from src.volatility.risk_authority import create_risk_authority

# Run emergency brake
emergency_brake = EmergencyBrakeEngine()
emergency_state = emergency_brake.run()

# Apply to risk authority
risk_authority = create_risk_authority()
if emergency_state['emergency_active']:
    risk_authority.trigger_emergency_override(
        exposure_cap=emergency_state['emergency_cap'] / 100.0,
        triggered_by='emergency_brake',
        reason=f"Emergency brake triggered: {emergency_state['risk_level']}"
    )
```

### Portfolio Risk Controller Integration

```python
from src.risk.portfolio_risk_controller import PortfolioRiskController
from src.volatility.risk_authority import create_risk_authority

# Run portfolio risk control
controller = PortfolioRiskController()
controller.apply_risk_controls()

# Risk authority automatically enforces limits during trade validation
risk_authority = create_risk_authority()
result = risk_authority.validate_trade(trade, portfolio, regime='low-vol')
```

### Liquidity Kill Switch Integration

```python
from src.risk.liquidity_kill_switch import LiquidityRiskAssessor
from src.volatility.risk_authority import create_risk_authority

# Assess liquidity risk
assessor = LiquidityRiskAssessor()
liquidity_df = assessor.run()

# Use liquidity data in trade validation
if liquidity_df is not None:
    frozen_positions = liquidity_df[liquidity_df['status'] == 'FROZEN']
    # Reject trades in frozen positions
```

---

## Migration Checklist

- [ ] Update all imports from old risk components to `src.volatility.risk_authority`
- [ ] Replace `UnifiedRiskCoordinator` usage with `UnifiedRiskAuthority`
- [ ] Replace `RiskAuthority` (cohesion) usage with `UnifiedRiskAuthority`
- [ ] Replace `RiskEngine` (cohesion) usage with `UnifiedRiskAuthority`
- [ ] Update trade validation logic to use `validate_trade()`
- [ ] Update emergency override logic to use new API
- [ ] Update risk invariant validation to use new methods
- [ ] Test all risk management workflows
- [ ] Update configuration files if needed
- [ ] Update documentation and comments

---

## Testing

After migration, test the following:

1. **Trade Validation**
   - Position size limits
   - Sector exposure limits
   - Greeks limits
   - Concentration limits

2. **Emergency Override**
   - Trigger emergency override
   - Validate trades under emergency
   - Clear emergency override

3. **Emergency Actions**
   - Crisis detection
   - De-risking actions
   - Stop-loss triggers

4. **Risk Invariants**
   - Capital conservation (R1)
   - Crisis de-risking (R2)
   - Risk-of-ruin protection (R3)
   - Position size limits (R4)

5. **Regime Adaptation**
   - Crisis regime limits
   - High-vol regime limits
   - Low-vol regime limits
   - Transition regime limits

---

## Rollback Plan

If issues arise, you can temporarily rollback by:

1. Copy archived files back to original locations:
   ```bash
   cp archive/deprecated/risk/unified_risk_coordinator_v1.py src/risk/unified_risk_coordinator.py
   cp archive/deprecated/risk/risk_authority_v1_cohesion.py src/cohesion/risk_authority.py
   cp archive/deprecated/risk/risk_engine_v1_cohesion.py src/cohesion/risk_engine.py
   ```

2. Revert imports in affected files

3. Report issues for investigation

---

## Support

For questions or issues with migration:
- Review this guide
- Check `src/volatility/risk_authority.py` implementation
- Review test examples in the codebase
- Consult the Unified Volatility Engine design document

---

## Archived Files

All deprecated risk components are preserved in `archive/deprecated/risk/`:

- `unified_risk_coordinator_v1.py` - Original unified risk coordinator
- `risk_authority_v1_cohesion.py` - Original risk authority from cohesion
- `risk_engine_v1_cohesion.py` - Original risk engine from cohesion

These files are kept for reference and potential rollback if needed.
