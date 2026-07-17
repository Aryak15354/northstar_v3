# Northstar V3

**A regime-aware portfolio operating system for Indian equities, with deterministic risk governance and CI-gated runtime integrity.**

Northstar V3 is a quantitative research-and-portfolio platform for the Nifty-500
universe. Its distinguishing bet is not a single alpha signal — it is an
*integrity-first* architecture: the system is engineered so that data leakage,
unit-mixing, silent model degradation, and fabricated outputs are caught by
automated gates *before* they can reach a portfolio decision. The interesting
engineering here is the machinery that makes the numbers trustworthy.

> **Status — stated honestly.** This is a research and advisory/paper-trading
> system, not a live-capital trading desk, and nothing here is investment
> advice. Portfolio NAV is walk-forward / paper; live operation runs in
> shadow (advisory) mode. Performance figures are intentionally **not**
> headlined in this README — the artifacts that back them are dated and
> regenerated, so they belong in the generated reports under `reports/`, not in
> marketing copy.

---

## Why this project is interesting

Most quant repos lead with a backtest curve. Northstar V3 leads with the
guardrails, because in systematic investing the expensive failures are silent
data lies, not bad ideas.

- **CI enforces truth, not just style.** Every push runs `make ci` → a suite of
  static integrity gates plus the test suite (see [`.github/workflows/ci.yml`](.github/workflows/ci.yml)).
  The gates include synthetic-**leakage** detection across the live-money path,
  duplicate-truth-source detection, execution-bypass guards, point-in-time
  enforcement, risk-clock injection checks, policy immutability, secret
  scanning, and price-continuity checks. A gate failure fails the build.
- **Live-artifact invariants.** Beyond static gates, `make invariants` runs
  truth checks over *live* artifacts — flagging unit mixing (₹ vs ₹cr),
  degenerate per-stock output, dead feeds, silently-failing schedulers, or a
  book that isn't the book the system intends to hold.
- **A single source of truth.** A canonical market-state spine feeds every
  engine, with per-panel freshness tracking so a stale input surfaces as a
  visible "stale" state rather than a confident-looking wrong number.
- **Regime awareness end-to-end.** Macro-transmission and macro-impact engines
  translate an RBI-anchored macro chain into regime labels that condition factor
  scoring, valuation, sizing, and risk.
- **Built to distrust itself.** Recent work deliberately deleted fabricated
  dashboard data, added model-provenance tracking to detect a silent
  FinBERT→lexicon sentiment fallback, enforced honest walk-forward NAV, and
  corrected fundamentals unit mixing — the changelog is a campaign against
  self-deception.

---

## Architecture

The engine lives under `src/` as ~45 domain modules, orchestrated over a
canonical state spine:

```
Ingestion      → RBI macro, prices, fundamentals, alt-data, corporate actions
                 (point-in-time enforced, cross-asset feeds)
Preprocessing  → canonical panels; ₹/₹cr unit discipline; PIT boundaries
State spine    → unified market-state, per-panel freshness truth
Macro engines  → macro_transmission_engine, macro_impact_engine → regime labels
Signals        → factors, signal_engineering, scoring, valuation, sentiment (NLP)
Portfolio      → portfolio construction, sizing, options strategy library
Risk           → deterministic risk governance, z-scaled limits, drift checks
Execution/PnL  → execution realism, honest walk-forward NAV, paper/advisory fund
Validation     → provenance, governance, OOS/forward validation, stress tests
Reporting      → dashboards (Brain Window / Streamlit), status & EOD reports
```

Supporting layers: `alpha_os`, `orchestrator`, `scheduler`, `automation`,
`diagnostics`, `live`, `runtime`, `intelligence`, `manifold`, `volatility`.

- **Universe:** Nifty-500 Indian equities (`universe/nifty_500.csv`).
- **Stack:** Python 3, pandas 2 / numpy 2, scikit-learn, XGBoost, CatBoost,
  Streamlit, Pydantic v2, pytest. (`requirements.txt`)
- **Scale:** ~2,900 Python modules across `src/`, `scripts/`, and `tests/`.

---

## Quick start

Northstar V3 runs fully local (no cloud dependency). The **Makefile is the
interface** — it mirrors CI, so `make ci` locally is the same check CI runs.

```bash
# 1) One-time setup
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 2) See what's available and check the system
make surface        # discover entry points and current surface
make doctor         # environment / dependency health check
make status         # system status report

# 3) Run the integrity checks (this is the heart of the project)
make gates          # static integrity gates (18 in the target; no live data needed)
make test           # pytest over tests/ and src/
make ci             # gates + tests — exactly what GitHub CI runs
make invariants     # truth checks over live artifacts (run post-refresh)

# 4) Operating rhythm
make preopen        # pre-market preparation
make morning        # morning run
make eod            # end-of-day processing
make dashboard      # launch the Brain Window dashboard (Streamlit)
```

The low-level surface/doctor/catalog tooling lives in `scripts/ns.py`; CI gates
live in `scripts/ci/`.

---

## Testing & CI

```bash
make ci             # static gates + full pytest suite (mirrors CI)
make test-fast      # focused subset: nlp, options, pnl, core
make test-collect   # collect-only, to sanity-check test discovery
```

CI ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) runs `make gates`
then `make test` on every push, so a merge cannot introduce a leakage/contract
violation or a red test without the build going red. On a bare checkout with no
live data, gates and invariants stay green by design (data-dependent checks
SKIP rather than fail).

---

## Validation

A component-level validation harness exercises the Phase 5/6 infrastructure —
provenance, execution-realism, governance, signal-decay and redundancy
monitoring, out-of-sample and forward validation. The most recent run
([`data/validation/final_institutional_validation_report.json`](data/validation/final_institutional_validation_report.json))
reports `MOSTLY_PASSED` with 10 of 11 components operational. This validates
that the *machinery* is wired and behaving, not that any strategy is profitable —
those are separate questions answered (and re-answered) by the walk-forward and
stress artifacts under `reports/` and `data/`.

---

## Honest limitations

- **No headline track record.** NAV is walk-forward / paper and regenerated;
  this README deliberately does not quote return numbers, because a fixed number
  in a README rots the moment the artifact behind it is rebuilt.
- **Advisory / shadow mode.** The system produces intended books and advises;
  it is not wired to live-capital execution.
- **Data-dependence.** Output quality is bounded by feed freshness and
  coverage — which is exactly why so much of the codebase is spent detecting
  when a feed is stale, degraded, or lying.
- **Indian-equity scope.** Universe, calendars, and units (₹/₹cr, market
  holidays) are India-specific.

---

## Repository notes

- `src/` — the engine (~45 modules). `scripts/` — operations, CI gates, tooling.
- `archive/` — retired code, isolated from active imports by a CI gate.
- Long local jobs: run inside `tmux`/`screen` to survive disconnects.

## Disclaimer

For research and educational purposes only. This is **not** investment advice.
Systematic trading involves substantial risk of loss; past behaviour of any
model or backtest is not indicative of future results.
