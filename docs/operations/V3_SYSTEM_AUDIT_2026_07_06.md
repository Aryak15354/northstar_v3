# V3 System Audit — 2026-07-06

Evidence-first investigation of the whole V3 system (same method as the
portfolio and options audits). Every claim below was verified against live
artifacts and code on 2026-07-06; nothing is taken from self-certification
reports.

**Headline:** the system's *plumbing shell* (NSE scrapers, sentiment, options
organ, paper fund) is alive and fresh, but the **core intelligence chain has
been dead for 100+ days** and several layers actively fabricate or mask their
own failure. The dashboard was faithfully displaying March-era intelligence as
if it were current.

---

## CRITICAL

### C1 — Production market state was FABRICATED by a CI fast-path
- `scripts/force_market_update.py` has a "fast refresh" mode (env
  `NORTHSTAR_FAST_MARKET_REFRESH` / `NORTHSTAR_CI_GATE`) that writes a **stub**
  `data/processed/market_state.parquet` with `regime: ci_fast_refresh`,
  `health_score: 1.0`, `allowed_exposure: 1.0` (maximum risk-on) and reports
  `pipeline_status: SUCCESS`.
- Evidence it fired in production: `data/processed/market_refresh_status.json`
  (2026-06-24, `mode: ci_fast_path`); row 0 of `market_state.parquet`;
  `unified_state_history.parquet` contains persisted `market_regime =
  'ci_fast_refresh'` rows — the fabrication contaminated the canonical record.
- Leak vector: `scripts/run_complete_v3_system.py --quick` sets
  `NORTHSTAR_FAST_MARKET_REFRESH=1` (line ~1542).
- **Fix:** stub writers must never touch canonical paths — write to a
  CI-scoped path, or hard-fail if the canonical path is targeted outside CI;
  purge `ci_fast_refresh` rows from state history.

### C2 — The core intelligence chain is unscheduled and has been dead ~100 days
- Freshness sweep (age in days on 2026-07-06): processed prices **101**,
  scores **101**, valuation **97**, valuation_engines **188**,
  alpha_os_timeseries **113**, strategy_posteriors **121**, strategy_regret
  **115**, exposure_history **170** — while NSE alt data / sentiment /
  announcements are 0–3 days fresh.
- Root cause: the raw→processed price merge (`src/processing/price_processor.py`)
  and the whole artifact chain (scores → valuation → alpha OS → market state)
  are driven **only** by `scripts/runners/refresh_v3_artifacts.py`, which is in
  **no schedule** (not in `config/refresh_cadence.yaml`, not in the daemon).
  It was last run manually in early March.
- Consequence: raw per-ticker prices reach **2026-06-23** but every consumer
  reads panels frozen at **2026-03-27**. `portfolio_weights.parquet` was
  regenerated on Jun 3 **from March scores**.
- **Fix:** add the artifact chain to the daily cadence (after data sources,
  before options/paper-fund steps), or fold `price_processor` + scorer +
  market-state into `downstream:` of the cadence file.

### C3 — Equity price ingestion is broken and lies about it
- `yfinance` downloads currently fail **100%** with
  `JSONDecodeError('Expecting value: line 1 column 1 (char 0)')` (verified
  live with `src/ingestion/price_fetcher.py --max-tickers 3`); raw CSVs frozen
  at 2026-06-23.
- Failure masking, three layers deep:
  1. the fetcher prints `✅ TICKER: N rows` from **old cached rows** when the
     download failed;
  2. `IntegratedDataPipeline.update_yfinance_market_data` catches price-fetch
     failure, prints a warning, and **returns success** if indices fetched;
  3. the refresh scheduler persists only successes — `equity_prices` has **no
     entry at all** in `data/runtime/refresh_state.json`, and the `failed`
     report goes to stdout that nobody reads.
- **Fix:** repair the fetch (yfinance version bump / session headers / switch
  to NSE bhavcopy as primary), make the fetcher exit non-zero when >N% of
  downloads fail, persist failures + consecutive-failure counts in
  refresh_state, and surface them on the dashboard What-Changed/ops panel.

### C4 — Nothing runs automatically: daemon stopped since Jun 24
- `data/options/live/northstar_daemon_status.json`: `status: "stopped"`,
  2026-06-24 — its final act was the C1 fabrication at 00:11 that morning.
- No daemon / refresh process is running (`ps` verified). All "fresh" data
  since is from manual runs.
- **Fix:** restart discipline (launchd/cron), and a dashboard ops light that
  goes RED when the daemon heartbeat ages > 1 day (see H5).

---

## HIGH

### H1 — Alpha OS regime model is decorative (92% degenerate)
- 315/344 rows (92%) of `alpha_os_timeseries.parquet` carry **uniform 0.25**
  regime posteriors with `regime_confidence = 0`; 12 rows `mode='error'`,
  17 `mode='blocked_contract_violation'` (everything zeroed);
  `alpha_os.strategy_weights` in unified state is **`{}`** — Alpha OS has
  never actually allocated.
- The dashboard charts these as if they were live beliefs.
- **Fix:** treat uniform-posterior rows as "no signal" (grey out / suppress),
  investigate why the HMM never converges (probably starved by C2's stale
  inputs), and gate the chart on `regime_confidence > 0`.

### H2 — `market_state.parquet` has no owner and no history
- 6+ writers found, including **`scripts/create_comprehensive_sample_data.py`,
  `scripts/create_sample_dashboard_data.py`, `scripts/demo_intelligence_observer.py`**
  (sample/demo generators writing the canonical path), plus recovery scripts
  and the C1 stub. File currently holds **2 rows** — history is overwritten,
  so any "regime history" surface is impossible.
- **Fix:** single owner module that *appends*; demo/sample scripts must write
  under `data/testing/`.

### H3 — Sentiment layer distorts rather than informs scores
- `scores.parquet` sentiment_multiplier: **475/500 names get a constant 1.1**
  (a flat +10% bias, not signal), 18 get 0.66, and **7 names are hard-zeroed
  (×0.0)** — score annihilation by sentiment alone (ALKEM, LEMONTREE,
  MAPMYINDIA, PFIZER, RPOWER…).
- `market_state` claims `sentiment_status: success` while its sentiment
  summary is **92 days old** (133,237 minutes).
- **Fix:** continuous multiplier with a floor (never ×0), and staleness must
  flip status to degraded.

### H4 — Valuation engine stack: 10% coverage, 6 months stale
- `valuation_engines.parquet`: **50 of 500** names, dated **2025-12-29** —
  the DES "Valuation Engine Stack" panel shows Dec-2025 gaps.
- **Fix:** schedule engine run across the full universe with the artifact
  chain (C2), or clearly label partial coverage.

### H5 — Heartbeats lie
- `live_engine_heartbeat.json` says `status: "alive"` with timestamp
  **2026-06-03** (33 days old). The dashboard's LIVE badge derives from stale
  artifacts and shows PREOPEN/WEEKEND instead of "engine down 12 days".
- **Fix:** a heartbeat is only "alive" if younger than N minutes; the global
  bar should show DOWN + age otherwise.

### H6 — `prices.parquet` scale corruption (pre-2025) — still latent upstream
- ~5 tickers (incl. **TCS.NS** 34×, **RELIANCE.NS** 8×) have pre-2025-01-01
  prices at the wrong scale (unadjusted split/scale error; e.g. TCS ₹115 →
  ₹3,974 overnight on the 2025-01-01 holiday row).
- The paper-fund engine self-heals (`MarketData._sanitize`), but **every other
  consumer is exposed** — momentum/vol signals in `strategies.py`, backtests,
  research labs computed across that boundary are corrupted (it produced a
  fake +128% Piotroski before the fix).
- **Fix:** repair at source in the canonical price builder (same back-adjust
  logic), and add a CI gate: no >2.5× single-day close ratio in the canonical
  panel.

---

## MEDIUM

- **M1** `exposure_history.parquet` has **1 row** (170 days old) — dead artifact
  that dashboards still list as a dependency.
- **M2** CI gate `check_risk_drift_literals` is red on **false positives** —
  it flags `0.02` inside CSS `rgba(...,0.02)` strings in dashboard code.
  Gate should exclude string literals / rgba patterns.
- **M3** Refresh failure reports are ephemeral: `daily_data_refresh.py` prints
  a JSON report and exits; failures are never persisted or alerted (compare:
  5 sources in state, 4 configured sources missing from it entirely —
  equity_prices, cross_asset, alt_data_nse_daily, options_suggestions).
- **M4** Benchmark (NIFTY-50) has **no ingestion source** — canonical was
  frozen at Jan 30; the paper-fund driver now opportunistically chains a stale
  side file (to Mar 14). A real index fetch belongs in the cadence.
- **M5** 11 `except → pass/continue` in `src/portfolio/` legacy modules
  (governor/coordinator) — failures vanish.
- **M6** Upstox token workflow: `.env.options` token expired 2026-07-06 03:30;
  options live-chain provider degrades silently (documented seam, but there's
  no dashboard indicator of token staleness).
- **M7** `strategy_weights.parquet` referenced by dashboards doesn't exist /
  state block empty (consequence of H1) — one honest placeholder remains.

---

## What is actually healthy (verified)
- NSE alternative data, announcements, credit ratings, bulk deals: 0–3 days.
- News/ticker sentiment ingestion: fresh to 2026-07-05 (raw side).
- Options organ suggestions + history: fresh (Jul 5), consistent.
- Paper fund (₹100cr): NAV/cash/positions reconcile to the rupee across
  unified_state, governor and nav_history; 163 tests green; honest horizon.
- Kill-switch / trading-halt gate: real, single canonical flag, tests pass.
- CI gates: green except the M2 false-positive gate.

## Suggested fix order
1. C3 fetch repair + C2 scheduling (unfreezes the whole chain)
2. C1 stub quarantine + purge contaminated history rows (+ C4 daemon restart)
3. H2 single-owner market state, H5 honest heartbeats
4. H6 upstream price repair + CI gate
5. H1/H3/H4 intelligence-quality work (post-unfreeze, since they're starved by C2)
6. M-tier cleanups

---

# RESOLUTION — same day (2026-07-06)

All C/H/M findings remediated and verified (163 tests green, all 18 CI gates pass):

- **C3 FIXED**: yfinance 0.2.48→0.2.66 (curl_cffi transport); 497/501 tickers fetched to 2026-07-06; `auto_adjust=True` pinned (mixed-adjustment fetches were the origin of H6); fetcher exits non-zero when >50% fail and no longer prints ✅ from cache; pipeline reports price failure as day failure.
- **C2 FIXED**: raw→processed merge + full v3 artifact chain wired into `config/refresh_cadence.yaml` `downstream:`; chain run — **scores (497), market state, portfolio weights (57), narratives all dated 2026-07-06**. Root blocker also fixed: `models/regime_models/` was EMPTY — retrained 4 regime models (incl. live regime; script's own overfit warning retained, honest). Retraining unblocked via shared PIT ruleset (`src/research/feature_pit_rules.py`) + Kaggle-profile strictness config.
- **C1 FIXED**: stub writer never overwrites an existing canonical market state; stub relabeled `ci_stub_no_signal` with `allowed_exposure 0.0` (can never authorise risk); purged 1 fabricated market_state row + **42 contaminated state-history rows**; retention guard refuses to re-absorb `ci_*` regimes.
- **C4 FIXED (one manual step remains)**: daemon startup crash fixed (governance_events mixed-type timestamp); daemon now fails SAFE with a logged `clock_drift_excessive` event. It refuses to run because the machine clock is genuinely **14.5s off NTP** (guard working as designed). → USER ACTION: sync system clock (`sudo sntp -sS time.apple.com` or System Settings → Date & Time), then `nohup python3 scripts/northstar_daemon.py --low-power &`.
- **H1 FIXED (display)**: uniform/zero regime posteriors suppressed as no-signal in dashboards; real fix is retrained models + unfrozen inputs.
- **H2 FIXED**: `MarketStateEngine.save_market_state` retention 90d→5y, refuses `ci_*` rows; sample/demo scripts redirected to `data/testing/sample_processed/`.
- **H3 FIXED**: sentiment multiplier floor 0.3 (never ×0 annihilation).
- **H4 FIXED**: `[:50]  # Limit for testing` cap removed from `valuation_engines.compute_universe_valuations` — full-universe run scheduled.
- **H5+M6 FIXED**: live badge shows `DOWN <N>d` when no runtime signal <2d old regardless of market session; Upstox token age in global-bar tape.
- **H6 FIXED at source**: `src/data/price_sanitizer.py` back-adjusts in `price_processor` (86 tickers healed); new CI gate `check_price_continuity` (registered in Makefile) enforces no >2.5×/<0.4× daily ratios — PASS on 500 tickers.
- **M1**: exposure_history regenerated from the one truth (501 daily rows). **M2**: rgba()/CSS-unit false positives masked — gate PASS. **M3**: scheduler persists `consecutive_failures`/`last_error`/`last_failure_utc`. **M4**: real NIFTY source (`scripts/update_benchmark_nifty.py`, daily cadence) — canonical rebuilt from true ^NSEI levels 2020→today. **M5**: governor history + config loads now log instead of pass.
- **BONUS finding fixed**: the Phase-D benchmark return-chaining had inflated NIFTY (+21.4% fake vs **−3.4% true**); chaining retired, full rebuild from real levels. Honest race now: **v3 +36.4% (Sharpe 0.75) vs NIFTY −3.4%**, famous strategies −6% to −20%.

Remaining known-and-accepted: valuation deep refresh running (quarterly step); daemon awaits clock sync; regime-model train ICs flagged high by the script's own guardrail (placeholder models until Kaggle alpha).
