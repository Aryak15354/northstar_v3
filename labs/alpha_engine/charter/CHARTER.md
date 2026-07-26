# CHARTER — Alpha Engine Lab (Programme A)

```
Version:            v1.0
Status:             Frozen
Freeze Date:        2026-07-26
Owner:              Aryak
Depends On:         docs/FIELD_REPORT_2026_07_26.md, GEN8_RESEARCH_CHARTER.md (governance inherited),
                    GEN5_RESEARCH_CONSTITUTION.yaml (Universal Oracle Ladder, for economic claims)
Supersedes:         — (first lab-era charter)
Related Registries: research_os/MASTER_EXPERIMENT_REGISTRY.csv (ALPHA-NNN)
```

## Objective

**Find and validate new sources of return.** One sentence, and it is the whole mandate: can we make
more money. Every other lab exists because this one needs inputs it cannot produce itself
(mechanism explanations from Microstructure, structural theory from Market Science) or because a
discovery it makes needs extraction work this lab should not do itself (Portfolio Engineering).

## Scope

Cross-sectional and time-series return prediction on Indian equities and the carrier universes this
programme has already established access to (FX, commodities, rates via Gen-7's frozen carrier
panel; options positioning and F&O flow via the Gen-8 microstructure layer). New candidate signals,
new universes, new capital-scale regimes, new combinations of already-validated signals.

## What this lab is explicitly NOT allowed to do

- **Publish a "finding" without the full pipeline**: pre-registration → power precheck → discovery →
  multiple-testing correction → rolling-window artifact check (where applicable) → out-of-sample
  validation → economic gate under the Universal Oracle Ladder. A result that skips any stage is not
  a finding; it is a candidate, and must be labeled as such.
- **Introduce a new predictive signal under cover of a portfolio-construction change.** Sizing,
  hedging, and execution-schedule questions belong to Portfolio Engineering. If a proposed change
  would alter *what* gets predicted rather than *how much capital* is put behind an existing
  prediction, it is not this lab's work to do alone — route it through Portfolio Engineering's
  charter boundary explicitly, or co-register it jointly (see the 2026-07-26 Delivery/liquidity-
  gradient joint test as the precedent for how a joint registration is done).
- **Claim validation from a single estimator, a single window, or a single capital level.** Every
  positive result must be shown to survive at least one adversarial attack analogous to the Gen-8
  capital-sweep stress test (survivorship, multiplicity, tradeability) before being called anything
  stronger than a lead.
- **Re-open a permanently retired direction without new evidence.** Representation learning
  (GRU/LSTM/autoencoder/transformer) on the existing panel and cross-asset transmission scans without
  a resolved power/design problem are both explicitly paused — see
  `labs/alpha_engine/decision_log/DECISION_LOG.md`, Phase 3 entries. Reopening either requires stating,
  in the pre-registration, what is genuinely new (a different data modality, not more of the same
  panel; a resolved design question, not another scan).

## Validation standard

**Statistical + economic + robustness, all three, every time.**

1. **Statistical**: a valid p-value (never `k/N` floored at zero — `scripts/gen8/lib/valid_pvalue.py`
   / `research_os/valid_pvalue.py`), multiple-testing corrected (BH, and BY wherever the test family
   is dependent — which is the default assumption, not the exception, for anything sharing a response
   series).
2. **Economic**: realizable Sharpe after simulated forecast-skill degradation against the canonical
   Config-4 benchmark (Universal Oracle Ladder, `GEN5_RESEARCH_CONSTITUTION.yaml` U1–U6). Raw
   backtest Sharpe is never a promotion basis. IC is not alpha — the programme's oldest banked lesson.
3. **Robustness**: survives the specific attacks this programme has already learned it needs —
   survivorship/truncation exposure, multiplicity-adjusted significance (not just the best cell of a
   search), and tradeability at the capital level actually being claimed (participation vs. ADV).

## Inherited governance (binding, not optional)

- Pre-registration before any result-producing code runs (`research_os/preregistration_template.md`).
- Power disclosure is a precondition for a gate, not a post-hoc diagnostic (Amendment-002, Gen-7,
  made structural via `research_os/power_precheck.py`) — a gate that cannot state its own minimum
  detectable effect before running does not get to run.
- The rolling-window artifact check (`research_os/rolling_window_artifact_check.py`) on any windowed
  feature involved in a persistence, memory, or autocorrelation claim — **with the Gen-8 correction
  carried forward exactly**: first-differencing is a conservative one-directional screen, not a clean
  discriminator (it can suppress genuine signal in a highly-persistent process just as it suppresses
  construction artifacts). State this caveat inline in any report using the check; do not run it
  silently as if it were dispositive on its own.
- Never-silently-rewrite-history: frozen results (`results/gen1..gen8/`, `docs/gen*_protocols/`) are
  read-only reference. New work lives under `labs/alpha_engine/`.
- Honest reporting of negative and inconclusive results as complete, citable outcomes — not lesser
  ones. A result that is UNRESOLVED because a design lacked power is a different, equally valid
  outcome from one that is REJECTED because the effect was tested for and not found. Never conflate
  the two (see `verdict_schema.py`).
- Self-caught corrections are disclosed in `decision_log/DECISION_LOG.md` the same session they are
  found, including false starts. This repository's track record (13 self-caught corrections across
  6 generations, 2 more in Gen-8) is a real asset. Do not break the pattern to look clean.

## Experiment ID convention

`ALPHA-NNN`, assigned once, in order, by `research_os/experiment_registry.py`. Never reassigned.
Cross-referenced in `research_os/MASTER_EXPERIMENT_REGISTRY.csv` alongside every other lab's IDs.
