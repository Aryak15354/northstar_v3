# Dashboard Visual Connection Blueprint (2026-02-28)

## Current State
- Active chart emissions: 77
- Contract-managed (freshness-aware) charts: 26
- Live-surface chart emissions: 9
- Live-surface without contract: 0
- Freshness breaches in live contracts: 0

## Highest Impact Fixes
1. Expand chart registry coverage from 26 to all tactical charts (~40+) so each card has freshness SLA.
2. Add chart-family view model slices (market/risk/portfolio/news/options/intelligence) to avoid over-fetching in each section.
3. Add synchronized global date range and scope controls across all live/tactical cards.
4. Continue replacing repeated single-chart blocks with multi-layer cards where duplicate signals remain:
   - Market: regime + pressure + macro/news overlays in one card.
   - Portfolio: benchmark + allocation + edge health in one card set.
   - Risk: drawdown surface + crisis probability + entropy in one risk card.
5. Add section-level explanatory summaries before charts:
   - "What this means now"
   - "Why changed"
   - "What action to take"

## Recommended Connection Model
- One canonical dashboard view model artifact:
  - `dashboard_view_model_live.{pkl,json}` for live mode.
  - `dashboard_view_model_research.{pkl,json}` for research mode.
- One chart registry contract per displayed card:
  - `chart_id`, `required_data_keys`, `required_columns`, `freshness_sla_hours`, `degraded_mode`.
- One render path for live cards:
  - `_render_chart_with_contract(...)` only.
- One failure/telemetry path:
  - structured health event + strict-mode escalation for critical live sections.

## Layered Visual Architecture (Operational)
- Layer 1: Executive Live Surface
  - 5 primary tabs with 9 live contract cards, all freshness-badged.
- Layer 2: Tactical Drill-Down
  - family tabs, 3-6 cards each, shared date-range controls.
- Layer 3: Research Lab
  - collapsed by default, lazy-loaded, watermark + freshness state.

## Additional Hardening
- Add CI check to block new charts without explicit keys or without registry entry (for live/tactical sections).
- Add snapshot visual diff test for key live cards.
- Add stale-data banner propagation from chart-level to section-level status strip.
