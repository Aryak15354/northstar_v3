# 📁 Scripts Directory

Executable scripts for Northstar V3 system operations.

## 🚀 Main Entry Point

### `northstar_v3_unified.py`
**Primary system launcher** - Single entry point for all Northstar V3 operations.

```bash
# Launch dashboard (default)
python northstar_v3_unified.py

# System update
python northstar_v3_unified.py --mode update

# Live trading
python northstar_v3_unified.py --mode live

# Backtesting
python northstar_v3_unified.py --mode backtest --strategy momentum
```

## 📂 Subdirectories

### `launchers/` - System Launchers
- `launch_clean_terminal.py` - Clean terminal interface
- `launch_integrated_northstar.py` - Integrated system launch  
- `launch_northstar_terminal.py` - Northstar terminal
- `launch_unified_terminal.py` - Unified terminal

### `runners/` - Component Runners
- `run_market_brain_production.py` - Production market brain
- `run_portfolio_governor.py` - Portfolio construction
- `run_intelligent_market_state.py` - AI market analysis
- `run_market_brain.py` - Market brain development

### `tests/` - Test Scripts
- `test_dashboard_issues.py` - Dashboard functionality testing
- `test_market_brain.py` - Market brain validation
- `test_terminal.py` - Terminal functionality testing

### `utilities/` - Utility Scripts
- `update_all_systems.py` - System-wide updates
- `validate_market_brain_data.py` - Data validation
- `eod_options_pipeline.py` - Options data processing

## 🎯 Legacy Scripts (Moved to Root)

The following scripts are now organized in subdirectories:
- `northstar_*.py` files - Various system interfaces
- Individual component scripts moved to appropriate folders

## 🔧 Usage Patterns

### Development Workflow
```bash
# 1. Update all systems
python scripts/utilities/update_all_systems.py

# 2. Validate data
python scripts/utilities/validate_market_brain_data.py

# 3. Run tests
python scripts/tests/test_dashboard_issues.py

# 4. Launch system
python scripts/northstar_v3_unified.py
```

### Production Workflow
```bash
# Launch production system
python scripts/northstar_v3_unified.py --mode live

# Monitor with dashboard
python scripts/northstar_v3_unified.py --mode dashboard
```

---

**All scripts maintain backward compatibility with the new organized structure.**