# Dashboard Consolidation Notes

## Task 5 Status

### 5.1 Select Production Dashboard ✅ COMPLETE

**Selected Dashboard**: `src/dashboard/northstar_v3_ultimate_integrated_dashboard.py`

**Rationale**:
- Largest and most comprehensive (102K)
- Most recently updated (Feb 10, 2026)
- Documented as production-ready in multiple reports
- Includes all major V3 features:
  - Command Center
  - V3 Analytics Suite
  - Advanced V3 Intelligence
  - Wave Analysis
  - Dynamic Clustering
  - Portfolio Analytics
  - Real-Time Monitor
  - Automation Hub
  - Shadow Trader + Weekly Rebalance
  - Edge Half-Life + Liquidity Exit Risk
  - Options Panel (already integrated)

**Other Dashboard Files** (candidates for archiving):
- `northstar_v3_production_dashboard.py` (0 bytes - empty file)
- `production_grade_dashboard.py` (13K - smaller, less complete)
- `northstar_v3_dashboard_methods.py` (24K - helper methods only)
- Various other dashboard variants in subdirectories

### 5.2 Integrate Dashboard with Unified Volatility Engine ⏸️ DEFERRED

**Status**: Deferred to Phase 2

**Reason**: This task requires components that haven't been built yet:
- Greeks Aggregator (Task 10) - for real-time Greeks monitoring
- IV Surface (Task 9) - for volatility surface visualization
- Performance Monitor (Task 26) - for performance attribution

**Current Dashboard State**:
- Already has Options Panel integrated (completed in Task 18 of options-trading-system spec)
- Uses OptionsObserver pattern for real-time updates
- Consumes data from V3DataHub

**Integration Plan** (to be executed after Phase 2 completion):

1. **Add Volatility State Display**:
   ```python
   from src.volatility import VolatilityStateEngine, RegimeDetector
   
   # In dashboard render method:
   state_engine = VolatilityStateEngine()
   current_state = state_engine.get_current_state()
   
   # Display regime
   st.metric("Current Regime", current_state.regime.value)
   st.metric("IV Rank", f"{current_state.iv_rank:.1%}")
   ```

2. **Add Greeks Monitoring Panel** (after Task 10):
   ```python
   from src.volatility import GreeksAggregator
   
   greeks = GreeksAggregator()
   portfolio_greeks = greeks.aggregate_portfolio_greeks()
   
   # Display Greeks with safety bands
   col1, col2, col3 = st.columns(3)
   col1.metric("Delta", f"{portfolio_greeks.delta:.2f}")
   col2.metric("Gamma", f"{portfolio_greeks.gamma:.2f}")
   col3.metric("Vega", f"{portfolio_greeks.vega:.2f}")
   ```

3. **Add Regime Visualization** (after Task 9):
   ```python
   # Regime history chart
   regime_history = regime_detector.get_regime_history()
   fig = create_regime_timeline(regime_history)
   st.plotly_chart(fig)
   ```

4. **Add Performance Attribution** (after Task 26):
   ```python
   from src.volatility import PerformanceMonitor
   
   perf_monitor = PerformanceMonitor()
   attribution = perf_monitor.get_performance_attribution()
   
   # Display P&L breakdown by Greeks
   st.subheader("P&L Attribution")
   st.bar_chart(attribution.greeks_pnl)
   ```

## Dashboard Architecture

### Current Structure
```
src/dashboard/
├── northstar_v3_ultimate_integrated_dashboard.py  # PRODUCTION
├── v3_data_hub.py                                 # Data provider
├── components/
│   ├── options_panel.py                          # Options display
│   └── v3_sentiment_panel.py                     # Sentiment display
└── observers/
    └── options_observer.py                        # Real-time updates
```

### Proposed Volatility Integration
```
src/dashboard/
├── northstar_v3_ultimate_integrated_dashboard.py  # PRODUCTION
├── v3_data_hub.py                                 # Enhanced with volatility state
├── components/
│   ├── options_panel.py                          # Existing
│   ├── volatility_panel.py                       # NEW - Volatility state display
│   ├── greeks_panel.py                           # NEW - Greeks monitoring
│   └── regime_panel.py                           # NEW - Regime visualization
└── observers/
    ├── options_observer.py                        # Existing
    └── volatility_observer.py                     # NEW - Volatility state updates
```

## Files to Archive

Once dashboard consolidation is complete, these files can be archived:

### Empty/Incomplete Dashboards
- `northstar_v3_production_dashboard.py` (0 bytes)

### Superseded Dashboards
- `production_grade_dashboard.py` (smaller, less complete)
- Any dashboard files in `backups/` directories

### Helper Files (Keep)
- `northstar_v3_dashboard_methods.py` (may contain useful utilities)
- `v3_data_hub.py` (core data provider)
- `consistent_data_manager.py` (data management)
- All files in `components/` and `observers/` (modular components)

## Next Steps

1. ✅ Complete Phase 1 (System Cleanup) - Tasks 1-8
2. ⏳ Complete Phase 2 (Core Infrastructure) - Tasks 9-13
   - Task 9: IV Surface modeling
   - Task 10: Portfolio Greeks Aggregator
   - Task 11: Configuration Management
   - Task 12: State Persistence
3. 🔄 Return to Task 5.2: Integrate dashboard with unified volatility engine
   - Add volatility panels
   - Add Greeks monitoring
   - Add regime visualization
   - Add performance attribution

## Testing Plan

After integration:
1. Verify dashboard loads without errors
2. Verify volatility state displays correctly
3. Verify Greeks update in real-time
4. Verify regime changes are reflected
5. Verify performance attribution is accurate
6. Load test with multiple concurrent users

## Documentation Updates Needed

After integration:
1. Update dashboard README with new panels
2. Document volatility panel features
3. Update user guide with Greeks monitoring
4. Add regime interpretation guide
5. Document performance attribution metrics
