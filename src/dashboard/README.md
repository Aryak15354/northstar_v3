# Northstar V3 Canonical Dashboard

The dashboard stack is now consolidated into one modular canonical app with distinct static and live data layers:

- entrypoint: `src/dashboard/app.py`
- integrated renderer: `src/dashboard/integrated_dashboard.py`
- visual registry: `src/dashboard/registry.py`
- read contract: `src/dashboard/data_contract.py`
- static/live loaders: `src/dashboard/data/data_manager.py`
- live refresh controller: `src/dashboard/data/live_data_manager.py`
- layout chrome: `src/dashboard/layout/`
- section renderers: `src/dashboard/sections/`
- visual builders and legacy compatibility layer: `src/dashboard/visual_catalog.py`
- launcher: `launch_dashboard.sh`

Primary dashboard sections:

- `Overview`
- `Performance`
- `Market`
- `Sentiment`
- `Portfolio`
- `Risk`
- `Options`
- `Research`
- `Alpha OS`

Architecture highlights:

- `115` real-data visualization modules
- static and live surfaces split cleanly
- live runtime refresh every 5 minutes through Streamlit fragments
- canonical top bar with NAV, regime, risk, exposure, health, live status, and last-updated timestamp
- progressive disclosure with primary panels, advanced expanders, and deep-dive sub-tabs
- no synthetic data backfilling in unavailable states

Use the canonical dashboard guide here instead:

- [`docs/dashboards/NORTHSTAR_V3_CANONICAL_DASHBOARD_GUIDE.md`](../../docs/dashboards/NORTHSTAR_V3_CANONICAL_DASHBOARD_GUIDE.md)

Quick launch:

```bash
./launch_dashboard.sh --dev
```

Direct launch:

```bash
python3 -m streamlit run src/dashboard/app.py
```

## Development

### Adding a New Visual

1. Add or reuse a real dataset in `src/dashboard/data/data_manager.py`.
2. Add a builder in `src/dashboard/visual_catalog.py`.
3. Register the visual in `src/dashboard/registry.py` with:
   - `tab`
   - `subsection`
   - `level`
   - `data_dependency`
   - `data_source`
   - `refresh_frequency`
4. The section renderer will place it automatically in the right layer.

### Live Mode

- `Options` and `Risk` are the live tabs.
- Live runtime data is loaded through:
  - `load_live_options_data()`
  - `load_risk_runtime_data()`
- Live sections rerender independently via Streamlit fragments.
- `st.session_state["last_live_update"]` is the canonical live refresh marker.

### Filter System

Sidebar filters currently support:

- date range
- regime filter
- strategy filter
- asset class filter

### Testing

```bash
# Contract and dashboard validation
pytest tests/test_dashboard_data_contract.py -v
python scripts/validate_gap8_dashboard.py

# Streamlit smoke
python3 -m streamlit run src/dashboard/app.py
```

## Migration from Old Dashboards

### Deprecated Dashboards

The following dashboards are superseded by the unified dashboard:

1. `northstar_v3_ultimate_integrated_dashboard.py` (11,593 lines)
2. `production_grade_dashboard.py` (archived)
3. `northstar_v3_production_dashboard.py` (archived)
4. `volatility_dashboard.py` (2,964 lines) → Tab 5
5. `automation_dashboard.py` → Tab 6

### Launch Script Migration

Old launch scripts (deprecated):
- `launch_ultimate_dashboard.sh`
- `launch_dashboard.sh` (if existed)
- `start_dashboard.sh` (if existed)
- Various other dashboard launchers

New launch script:
- `launch_dashboard.sh` (single entry point)

### Parallel Operation

Before full cutover, run both dashboards:

```bash
# Old dashboard (port 8501)
./launch_ultimate_dashboard.sh

# New dashboard (port 8502)
./launch_dashboard.sh --port 8502
```

Compare numbers daily for 5 consecutive trading days before cutover.

## What's New in Gap 8

- Static vs live dashboard split
- One visual registry for all sections
- Real-data-only render contract
- Cleaner progressive disclosure for high chart density
- Dedicated live runtime surfaces for options and risk
- Institutional chrome and top-line control bar

## Support

For issues or questions:

1. Check this README
2. Review `GAP8_DASHBOARD_CONSOLIDATION_COMPLETE.md`
3. Run validation: `python scripts/validate_gap8_dashboard.py`
4. Review `src/dashboard/registry.py`
5. Review StateAuthority logs

## License

Part of Northstar V3 institutional trading system.
