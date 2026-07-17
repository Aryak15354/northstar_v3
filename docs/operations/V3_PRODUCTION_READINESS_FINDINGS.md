# V3 Production-Readiness — First-Draft Problem List

Cross-reference of the V3 documentation (the *intended* system) against the
*actual* codebase. Grouped by type; each item notes severity and whether it is
**OPEN** or **FIXED** (already addressed in recent remediation). Meant as a
working draft to attack before a deeper review pass.

---

## A. Documentation ↔ reality gaps (credibility / correctness)

1. **Test count overclaim — HIGH.** Doc §4 states "1,995 collected tests." Actual
   `pytest --collect-only` = **152** (49 active test files, 151 test functions).
   The 1,995 figure is the count of `test_*.py` *files across the whole disk
   including `_cold_archive/` (2,093 files)* — dead/archived tests pytest never
   runs. Any reviewer who runs the suite will see the gap immediately. Fix the
   stat to the real number and delete/quarantine archived test files.
2. **Self-certification docs contradict evidence — HIGH.** 21 `reports/system/*.md`
   still claim "PRODUCTION COMPLETE / CERTIFIED FOR CAPITAL DEPLOYMENT" while
   machine-generated diagnostics from the same period show POOR health. The doc's
   own §16 flags "historical docs overclaim" — but they're still in-tree and will
   be read as status. Purge or clearly mark them "superseded."
3. **`ns_uso/` is a data-exchange surface, not a code subsystem — LOW.** Repo
   layout (§4) presents `ns_uso/` as the "Northstar USO options subsystem," but it
   holds **0 Python files** — it is a live *data* directory (`ns_uso/exports/v3/*.parquet`:
   sentiment/narrative exports consumed by the trading orchestrator + options
   engine). Correct the doc to describe it as a data-exchange path, not a subsystem.
   (NOTE: earlier draft wrongly called this "empty/dead" — it is live; do not delete.)
4. **NEP test evidence — MED.** Execution-platform §21 cites "61 tests, 1 failed."
   That's a *different* repo (`Options_system`). If NEP is being folded into V3,
   its test suite must be brought in and counted, not cited from a separate tree.

## B. Architecture problems

5. **Research ↔ execution coupling (boundary leak) — HIGH.** The doc's core
   principle is "layers communicate through canonical files, not runtime coupling,"
   yet §16 admits "the research worker reads live options runtime state files."
   That violates the central design invariant and makes research results depend on
   live execution state (non-reproducible). Needs a clean snapshot-import contract.
6. **Two → (now three) options systems — HIGH / in progress.** v3 `src/options`,
   the standalone `Options_system` (NEP), and the doc even references `ns_uso`.
   The doc's stated design is *separation* (V3 = scores, NEP = execution, versioned
   file boundary); the recent work *unified* them into one `OptionsOrgan` inside
   v3. **These two directions conflict** — a deliberate decision is required:
   single-organ (what was just built) vs. two-systems-with-a-file-contract (doc).
7. **`config/research_policy.yaml` missing entirely — MED-HIGH.** Doc §16 says it
   "contains only a comment"; reality: **the file does not exist**. Code paths
   reference it (research governance, price-path override), so behavior silently
   falls back to code defaults — governance is not reviewable in config as claimed.
8. **Dual/legacy data pipelines coexist — MED.** Legacy `data/processed/prices.parquet`
   producer/consumer pipeline runs in parallel to the canonical PIT contract;
   two fundamentals pipelines (screener vs yfinance) were only just reconciled.
   The "single canonical source" claim isn't yet true across all consumers.

## C. Production blockers

9. **Manual Upstox token — HIGH (partially mitigated).** No automated OAuth; a human
   must paste a token daily or all live/options data stalls. FIXED: staleness is now
   detected + surfaced (banner, preopen fail) and non-Upstox data still flows. OPEN:
   the automated OAuth refresh the doc calls for.
10. **Empty options event calendar — HIGH.** `options_trading.yaml event_calendar: []`.
    Event-risk eligibility gating has nothing to gate on, so pre-earnings / RBI /
    budget blackouts are not enforced. Needs automated NSE event ingestion.
11. **No external failure alerting — MED-HIGH.** Cron/loop failures rely on log-file
    watching (doc §17). A silent overnight failure = stale data driving next-day
    decisions with no page. Needs email/Telegram/webhook alerting on failure.
12. **Reproducibility not enforced — MED-HIGH.** No pinned global seed / data-snapshot
    versioning at the research boundary; combined with (5) research reads live state,
    walk-forward results are not bit-reproducible. Needs versioned input snapshots.
13. **Dirty worktree — MED.** 205 changed/untracked entries; generated artifacts,
    deleted files, and source coexist. No clean tagged "submission/deploy" commit.
    Blocks a trustworthy release baseline.

## D. Brittleness / robustness

14. **Broad `except Exception` → neutral-default pattern (systemic) — HIGH.** Across
    intelligence/valuation/allocation, failures are swallowed and replaced with a
    plausible neutral value (confidence 0.5, NORMAL/0.8 exposure, fair-value≈price),
    so a broken upstream is indistinguishable from a healthy read. Several money-path
    instances FIXED; the *pattern* remains widespread and needs a lint/gate.
15. **cwd-dependent path resolution — MED.** Some loaders resolve against `Path.cwd()`
    not `PROJECT_ROOT`, so a cron/daemon subprocess in the wrong dir hard-crashes.
16. **Modeled-vs-live silent fallback — MED.** Options greeks/premia fall back to a
    model when no live chain; correct, but must always be *flagged* downstream (the
    organ flags `modeled`, but confirm every consumer respects it).
17. **Freshness by file mtime, not content date — MED (mostly fixed in ingestion).**
    Health/freshness scoring keyed on mtime can mark stale content "fresh" if any
    process touches the file. Content-date staleness now enforced in the loaders;
    audit the health-scoring path.

## E. Messiness / non-standard / hygiene

18. **V3/V4 naming drift — MED.** `options_trading.yaml` carries "Northstar V4 AlphaOS
    migration flags" inside the V3 system; `alpha_os` block present. Pick one identity.
19. **Enormous `scripts/` surface — MED.** Hundreds of one-off/fix/gap/validate
    scripts alongside the ~8 canonical entry points. Hard to tell live from dead.
    Quarantine non-canonical scripts; the catalog only lists a few.
20. **No automated CI historically — MED (now fixed).** Gates existed but nothing ran
    them. FIXED: `.github/workflows/ci.yml` + `make ci` now run gates + tests.
21. **Async pytest deprecation warning — LOW.** Set `asyncio_default_fixture_loop_scope`.
22. **Inconsistent persistence models — MED.** V3 = parquet/JSON + append-only ledger;
    NEP = SQLite/Postgres+Redis. A merged system needs one deliberate persistence story.

## F. Missing for production-grade

23. **Transaction-cost realism — MED (partially fixed).** Backtest now charges 15bps;
    doc §17 wants full STT + brokerage + market-impact. Extend the cost model.
24. **Walk-forward doesn't span full cycles — MED.** Validation history should cover
    2020 COVID, 2022 rate-hikes, 2024 election; quarterly fundamentals only reach
    ~2023 locally (free-source ceiling), which caps how far back factors validate.
25. **Factor decay / turnover analysis — MED.** No measured signal half-lives to set
    rebalancing frequency; without it, turnover + tax drag are unmanaged.
26. **Model governance is thin — MED (partially fixed).** Promotion gate now enforces
    IC/ICIR/hit-rate; still no walk-forward-significance requirement, no multiple-
    comparisons correction across the dozens of experiment reruns (p-hacking risk).
27. **Secrets/credential hygiene — verify.** `.env.options` is gitignored (good);
    confirm no token/secret has ever been committed in history before any public push.

## G. Already fixed in recent remediation (don't re-work)
- Kill-switch crash, NAV double-count, options risk-control unit mismatch, portfolio
  cap defeat, backtest look-ahead + costs, silent all-zero model scoring, model
  promotion gate, CI gate honesty, stale price path in decision path, state-file
  locking, TRADING_HALTED enforcement, NSE holiday calendar, gap-safe backfill.
