# Files Requiring Import Updates

This document lists all files that import the deprecated risk components and need to be updated to use the new `UnifiedRiskAuthority`.

## Files Importing UnifiedRiskCoordinator

These files need to update imports from `src.risk.unified_risk_coordinator` to `src.volatility.risk_authority`:

### Active Files (Need Updates)

1. **src/validation/institutional_walk_forward_validator.py**
   - Line 35: `from src.risk.unified_risk_coordinator import UnifiedRiskCoordinator`
   - Action: Update to use `UnifiedRiskAuthority`

2. **src/core/legacy_wrappers.py**
   - Line 205: `from src.risk.unified_risk_coordinator import UnifiedRiskCoordinator`
   - Action: Update to use `UnifiedRiskAuthority`

3. **src/core/organ_wrappers.py**
   - Line 1146: `from src.risk.unified_risk_coordinator import UnifiedRiskCoordinator`
   - Action: Update to use `UnifiedRiskAuthority`

4. **src/options/v3_risk_integration.py**
   - Line 26: `from src.risk.unified_risk_coordinator import UnifiedRiskCoordinator`
   - Action: Update to use `UnifiedRiskAuthority`

5. **scripts/verify_system_core_functionality.py**
   - Line 297: `from src.risk.unified_risk_coordinator import UnifiedRiskCoordinator`
   - Action: Update to use `UnifiedRiskAuthority`

6. **scripts/verify_system_operations.py**
   - Line 124: `from src.risk.unified_risk_coordinator import UnifiedRiskCoordinator`
   - Action: Update to use `UnifiedRiskAuthority`

### Backup Files (No Action Needed)

These are in backup directories and don't need updates:
- `backups/root_cleanup_archive_20260123_000918/...`
- `backups/pre_cleanup_20260117_013055/...`

---

## Files Importing RiskAuthority (Cohesion)

These files need to update imports from `src.cohesion.risk_authority` to `src.volatility.risk_authority`:

### Active Files (Need Updates)

1. **tests/validation/test_system_integration_validation.py**
   - Line 37: `from src.cohesion.risk_authority import RiskAuthority`
   - Action: Update to use `UnifiedRiskAuthority`

2. **tests/validation/test_task8_risk_management_properties.py**
   - Line 22: `from src.cohesion.risk_authority import RiskAuthority, RiskConfiguration, AuthorityLevel`
   - Action: Update to use `UnifiedRiskAuthority, RiskLimits, AuthorityLevel`

### Backup Files (No Action Needed)

These are in backup directories and don't need updates:
- `backups/root_cleanup_archive_20260123_000918/...`
- `backups/pre_cleanup_20260117_013055/...`

---

## Files Importing RiskEngine (Cohesion)

These files need to update imports from `src.cohesion.risk_engine` to `src.volatility.risk_authority`:

### Active Files (Need Updates)

1. **tests/validation/test_task8_risk_management_properties.py**
   - Line 22: `from src.cohesion.risk_engine import RiskEngine`
   - Action: Update to use `UnifiedRiskAuthority`

---

## Update Priority

### High Priority (Core System Files)
1. `src/core/legacy_wrappers.py`
2. `src/core/organ_wrappers.py`
3. `src/validation/institutional_walk_forward_validator.py`
4. `src/options/v3_risk_integration.py`

### Medium Priority (Scripts)
1. `scripts/verify_system_core_functionality.py`
2. `scripts/verify_system_operations.py`

### Low Priority (Tests)
1. `tests/validation/test_system_integration_validation.py`
2. `tests/validation/test_task8_risk_management_properties.py`

---

## Update Template

### For UnifiedRiskCoordinator → UnifiedRiskAuthority

**Old:**
```python
from src.risk.unified_risk_coordinator import UnifiedRiskCoordinator

coordinator = UnifiedRiskCoordinator()
success = coordinator.apply_unified_risk_management()
```

**New:**
```python
from src.volatility.risk_authority import create_risk_authority

risk_authority = create_risk_authority()
state = risk_authority.get_risk_state()
```

### For RiskAuthority (Cohesion) → UnifiedRiskAuthority

**Old:**
```python
from src.cohesion.risk_authority import RiskAuthority, RiskConfiguration, AuthorityLevel

risk_authority = RiskAuthority(config_manager, audit_logger)
```

**New:**
```python
from src.volatility.risk_authority import create_risk_authority, RiskLimits, AuthorityLevel

risk_authority = create_risk_authority()
```

### For RiskEngine (Cohesion) → UnifiedRiskAuthority

**Old:**
```python
from src.cohesion.risk_engine import RiskEngine

risk_engine = RiskEngine(config_manager, state_manager, risk_authority)
```

**New:**
```python
from src.volatility.risk_authority import create_risk_authority

risk_authority = create_risk_authority()
```

---

## Notes

- The specialized components (`emergency_brake.py`, `portfolio_risk_controller.py`, `liquidity_kill_switch.py`) should continue to be used as-is
- They integrate with the new `UnifiedRiskAuthority` rather than being replaced by it
- See `MIGRATION_GUIDE.md` for detailed API migration instructions
- Test thoroughly after updating each file
