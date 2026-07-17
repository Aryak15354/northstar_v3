# Options System Integration Map

Single source of truth for merging the standalone `Options_system`
("Northstar Execution Platform" + NIL) into one **OptionsOrgan** inside v3.
Every capability of the standalone system is tracked here so nothing is
silently dropped. Status legend:

- **PORTED** — reimplemented inside v3 (the unified system).
- **COVERED** — an equivalent already exists in v3.
- **SEAM** — an integration point exists in v3; the standalone module plugs in
  behind it (not yet wired to the live module, but not lost).
- **PENDING** — valuable, not yet integrated; explicitly queued.
- **DROP** — intentionally not carried over (redundant / obsolete).

## Unified system (what exists now, inside v3)

| Component | File |
|---|---|
| OptionsOrgan (suggestion brain: shorts/longs/hedges/opportunities) | `src/options/options_organ.py` |
| Black-Scholes pricer + greeks (any underlying, offline) | `src/options/black_scholes.py` |
| v3 signal → candidate feed (scorer + sentiment + prices + portfolio) | `src/options/candidate_builder.py` |
| Organ-bus registration | `src/core/organ_wrappers.py::OptionsOrganWrapper` |
| Daily entry point | `scripts/generate_options_suggestions.py` + cadence source `options_suggestions` |
| Strategy vocabulary, greeks agg, survival/kill-switch rules, trade ledger | pre-existing `src/options/*` |

## Standalone `Options_system` → integration status

| Standalone module(s) | Capability | Status | Where in v3 / plan |
|---|---|---|---|
| `oms/oms_server, state_machine, leg_group, position_manager` | Order management state machine | **SEAM** | Execution seam in OptionsOrgan; live OMS plugs into a future `execution_adapter`. Advisory path uses v3 shadow (`PortfolioRuntimeService`). |
| `oms/risk_checks, order_slicer` | Pre-trade risk validation + order slicing | **SEAM / COVERED** | v3 has `survival_rules_engine` (kill switches) + runtime risk gates; slicer ports with the live OMS. |
| `adapters/upstox_auth, upstox_adapter, oauth_loopback, upstox_symbol_map` | Upstox broker auth + orders + symbol map | **SEAM** | v3 `src/options/upstox_adapter.py` + the token flow (`refresh_upstox_token.py`). `chain_provider` seam consumes it for live chains. |
| `market_data/upstox_protocol, market_data_server, portfolio_stream_server, MarketDataFeed_pb2` | Live tick + portfolio websocket streams | **PENDING** | High value for live greeks/marks. Queue: port as a market-data feed behind `chain_provider`. |
| `nil/**` (fetchers, nlp, intelligence, training, evaluation) | News intelligence layer: article fetch → NLP/LLM reasoning → manipulation/opportunity detection → portfolio impact | **SEAM (news_overlay)** | `OptionsOrgan.attach_news_overlay()` + `CandidateBuilder(news_overlay=...)` accept a NIL overlay exposing `.scores()`. Live NIL port is PENDING; sentiment panel currently supplies the news term. |
| `signal_bridge/v3_bridge` | Validate + publish v3 signals | **PORTED** | Replaced by `candidate_builder.py` (reads v3 artifacts natively; no cross-repo bridge needed). |
| `strategies/momentum_v1, registry, capital_allocator, base_strategy` | Strategy set | **COVERED** | Audit found this thin (mostly momentum_v1); v3's strategy vocabulary + the organ's structure builders supersede it. |
| `db/repository, models, core/database`, `alembic/**` | DB-backed control plane + migrations | **DROP (for now)** | v3 persists via canonical parquet/JSON + trade ledger. A DB control plane is only needed for live multi-order OMS; revisit with live execution. |
| `runtime/supervisor` | Process supervision | **COVERED** | v3 `scripts/northstar_daemon.py` supervises processes. |
| `alerts/alert_service` | Alerting | **COVERED / SEAM** | v3 has health monitor + `TRADING_HALTED` gate; wire options alerts into it when live. |
| `dashboard/api, dashboard_api` | Dashboard | **COVERED** | v3 dashboard; add an options-suggestions panel reading the suggestions JSON. |
| `validation/phase2_metrics` | Metrics/validation | **PENDING** | Fold useful option metrics into v3 validation. |
| `core/config, bootstrap, universe, schemas, enums, streams, security` | Framework plumbing | **COVERED** | v3 config/state/universe frameworks. |
| `reconciliation/**`, `backtest/**` | Recon + backtest | **COVERED** | v3 `src/pnl/reconciliation.py` + backtest engine. |
| `adapters/mock_fill_engine` | Paper fills | **COVERED** | v3 shadow/paper execution. |

## Prioritized follow-on (queued, not lost)
1. **Live execution**: port `oms/*` + `order_slicer` behind an `execution_adapter`; wire `upstox_adapter`/market-data streams into `chain_provider` for live chains + marks. Gated by the Upstox token flow.
2. **NIL news layer**: port `nil/**` as a `news_overlay` exposing `.scores() -> {ticker: [-1,1]}`; attach via `OptionsOrgan.attach_news_overlay()` so event/manipulation signals sharpen shorts + hedges.
3. **Options dashboard panel** + **options metrics** into v3 validation.
