# Dashboard Integration Refoundation Plan (2026-02-28)

## Objective
Turn the current dashboard from artifact-by-artifact rendering into a single, coherent decision surface with deterministic data lineage and chart-level freshness contracts.

## 1) Introduce a Canonical Dashboard View Model
- Build one consolidated artifact: `data/processed/dashboard_view_model.parquet` (+ JSON metadata).
- Produce it at the end of update flow from the same snapshot timestamp.
- Include standardized fields for market, intelligence, portfolio, risk, options, sentiment.

## 2) Add Chart Registry + Contracts
- Create `src/dashboard/chart_registry.py` with one entry per chart:
  - `chart_id`
  - `section`
  - `owner_function`
  - `required_columns`
  - `freshness_sla_hours`
  - `degraded_behavior`
- Validate the registry in CI against actual chart calls.

## 3) Enforce Chart-Level Freshness in UI
- Show freshness badge on every chart (`fresh`, `stale`, `expired`).
- Block high-impact charts in Live mode when expired.
- Keep Research mode visible but clearly watermarked as stale.

## 4) Remove Dashboard Dead Surface
- Archive unreachable chart modules:
  - `src/dashboard/components/production_grade_panel.py`
  - `src/dashboard/strategy_intelligence_panel.py`
  - `src/dashboard/northstar_v3_dashboard_methods.py`
- Remove unreferenced chart functions from canonical dashboard:
  - `render_command_center`
  - `render_live_mode_compact`
  - `render_macro_valuation_compact`
  - `render_portfolio`

## 5) Replace Implicit Auto-Keying with Explicit Keys
- Keep guard as safety net, but add explicit stable `key=` for all active charts.
- Use deterministic naming: `<layer>_<panel>_<metric>`.

## 6) Unify Time Axes and Cross-Filtering
- Introduce one global date-range and one global scope filter (index/sector/strategy).
- Apply these filters consistently across Market/Intelligence/Portfolio/Risk/News.
- Avoid each panel silently choosing its own horizon.

## 7) Separate Live vs Research Payload Paths
- Live mode should load a minimal low-latency view model.
- Research mode can lazily load heavy artifacts (macro impact/transmission/valuation diagnostics).
- This avoids slow live renders and stale-heavy research artifacts polluting live decisions.

## 8) Tighten Error Policy
- Replace broad section swallowing in strict mode with hard panel failure telemetry.
- Keep user-facing error cards, but emit structured failure events to `data/processed/dashboard_health.json`.

## 9) Add Dashboard CI Gates
- New gate: chart registry completeness (100% call-site coverage).
- New gate: freshness SLA compliance for Live-critical charts.
- New gate: screenshot smoke diff for major tabs.

## 10) Runbook Integration
- Add dashboard validation to cutover runbook:
  - Live mode render smoke
  - Research mode render smoke
  - Freshness SLA report
  - Dead-surface check (no unreferenced chart functions)
