# 🚀 Northstar V3 Usage Guide

Quick reference for running all facets of the Northstar V3 system.

## 🔍 **System Health Check**

Always start by checking system status:

```bash
python check_system_status.py
```

This will show:
- ✅ Data availability (critical files present)
- 🕒 Data freshness (how old your data is)
- 🧩 Component status (all system parts working)
- 🏥 System health (dependencies, disk space, etc.)
- 📋 Recommendations (what to do next)

## 🧠 **Launch Brain Window Dashboard**

The latest and most advanced dashboard:

```bash
python launch_brain_window.py
```

- Opens at: http://localhost:8501
- Features: Real-time intelligence, unified state, decision support
- Use Ctrl+C to stop

## 🔄 **Complete System Pipeline**

### Quick Update (5-10 minutes)
```bash
python run_complete_v3_system.py --quick
```
- Updates data and system state
- Skips backtesting and validation
- Good for daily operations

### Full Pipeline (30-60 minutes)
```bash
python run_complete_v3_system.py
```
Runs complete pipeline:
1. 🔄 Data Ingestion (RBI + Market Data)
2. 🧠 System Update (Intelligence + Portfolio)
3. 🧪 Backtesting & Validation
4. 📊 Shadow Trading
5. 📈 Performance Analysis
6. 🖥️ Dashboard Launch

### Specific Components Only
```bash
# Data ingestion only
python run_complete_v3_system.py --data-only

# Backtesting only
python run_complete_v3_system.py --backtest-only

# Dashboard only
python run_complete_v3_system.py --dashboard-only
```

## 📊 **Individual System Components**

### Data Ingestion
```bash
# Complete data pipeline (RBI + Market)
python src/ingestion/integrated_data_pipeline.py

# RBI data only
python src/ingestion/rbi_daily_updater.py

# Market data only
python src/ingestion/price_fetcher.py
```

### Backtesting & Validation
```bash
# 12-month institutional validation
python scripts/institutional_12month_real_data.py

# Historical crisis testing (2008, COVID, 2022)
python scripts/demo_enhanced_stress_tests.py

# Walk-forward out-of-sample validation
python scripts/run_honest_walk_forward.py

# Final institutional validation
python scripts/final_institutional_validation.py
```

### Shadow Trading
```bash
# Run shadow trading for 1 day
python scripts/launch_comprehensive_shadow_trading.py --mode manual --days 1

# Run shadow trading for 5 days
python scripts/launch_comprehensive_shadow_trading.py --mode manual --days 5
```

### Performance Analysis
```bash
# Generate 12-month performance report
python scripts/generate_12month_performance_report.py

# System performance analysis
python scripts/run_alpha_validation.py
```

## ⚡ **Main Entry Point (Alternative)**

The unified entry point supports multiple modes:

```bash
# System update
python run.py --mode update

# Launch Brain Window
python run.py --mode dashboard --dashboard brain

# System health check
python run.py --mode health

# Live autonomous operation
python run.py --mode live

# Backtesting mode
python run.py --mode backtest --strategy momentum

# System status
python run.py --mode status
```

## 🎯 **Common Workflows**

### Daily Operation
```bash
# 1. Check system status
python check_system_status.py

# 2. Quick update if data is stale
python run.py --mode update

# 3. Launch dashboard
python launch_brain_window.py
```

### Weekly Validation
```bash
# 1. Full system pipeline
python run_complete_v3_system.py

# 2. Review performance reports in reports/
# 3. Check shadow trading results in data/live/shadow_trading/
```

### Monthly Analysis
```bash
# 1. Generate comprehensive reports
python scripts/generate_12month_performance_report.py

# 2. Run stress tests
python scripts/demo_enhanced_stress_tests.py

# 3. Validate walk-forward performance
python scripts/run_honest_walk_forward.py
```

## 📁 **Key Directories**

- `data/processed/` - System state files
- `data/raw/prices_daily/` - Market price data
- `data/macro/raw/` - RBI macro data
- `reports/` - Performance and validation reports
- `logs/` - System logs
- `src/dashboard/` - Dashboard implementations
- `scripts/` - Execution scripts

## 🔧 **Troubleshooting**

### Data Issues
```bash
# Force data update
python run_complete_v3_system.py --data-only --force-data

# Check data freshness
python src/ingestion/integrated_data_pipeline.py --check-only
```

### System Issues
```bash
# Comprehensive system check
python check_system_status.py

# Test system imports
python -c "from src.core.state import UnifiedState; print('✅ System imports work')"
```

### Dashboard Issues
```bash
# Direct dashboard launch
streamlit run src/dashboard/brain_window.py

# Alternative dashboard
python run.py --mode dashboard --dashboard unified
```

## 📊 **Performance Monitoring**

### Real-time Monitoring
- Brain Window dashboard shows live system status
- Check `data/processed/market_state.parquet` for latest market state
- Monitor `logs/` directory for system logs

### Historical Analysis
- Performance reports in `reports/performance/`
- Backtest results in `data/backtests/`
- Shadow trading results in `data/live/shadow_trading/`

## 🚨 **Emergency Procedures**

### System Not Responding
1. Check system status: `python check_system_status.py`
2. Check logs: `tail -f logs/system_run_output.log`
3. Restart system: `python run.py --mode update`

### Data Corruption
1. Check data integrity: `python check_system_status.py`
2. Force data refresh: `python run_complete_v3_system.py --data-only --force-data`
3. Verify results: `python check_system_status.py`

### Performance Issues
1. Run stress tests: `python scripts/demo_enhanced_stress_tests.py`
2. Check validation: `python scripts/final_institutional_validation.py`
3. Review reports in `reports/validation/`

---

## 🎯 **Quick Reference**

| Task | Command | Duration |
|------|---------|----------|
| System Check | `python check_system_status.py` | 1 min |
| Dashboard | `python launch_brain_window.py` | Instant |
| Quick Update | `python run_complete_v3_system.py --quick` | 5-10 min |
| Full Pipeline | `python run_complete_v3_system.py` | 30-60 min |
| Data Only | `python run_complete_v3_system.py --data-only` | 10-15 min |
| Backtesting | `python scripts/institutional_12month_real_data.py` | 20-30 min |
| Stress Tests | `python scripts/demo_enhanced_stress_tests.py` | 15-20 min |

---

**Need Help?** Check the main README.md for detailed system documentation.