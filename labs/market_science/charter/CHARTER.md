# CHARTER — Market Science Lab (Programme B)

```
Version:            v1.0
Status:             Frozen
Freeze Date:        2026-07-26
Owner:              Aryak
Depends On:         docs/FIELD_REPORT_2026_07_26.md, MSRP_CHARTER.md (inherited pillars, safeguards,
                    Rolling-Window Persistence Principle), results/msrp/PHASE1_SYNTHESIS_FROZEN.md
Supersedes:         — (MSRP itself is frozen and untouched; this lab is MSRP's successor in method,
                    not a reopening of MSRP's own frozen phases)
Related Registries: research_os/MASTER_EXPERIMENT_REGISTRY.csv (MSCI-NNN)
```

## Objective

**Build theory about what the market's information actually is and how it behaves — never a
portfolio.** This lab measures; it does not trade. Its unit of success is a falsifiable claim about
market structure (an information hierarchy, a memory profile, a regime dependency), not a Sharpe
ratio, a signal, or a recommendation for the live book.

## Scope

Continuation and escalation of MSRP's own question — "what is the market's predictive information
made of" — but moved from **descriptive** measurement (MSRP Phase 1/2: does information exist, how
is it organized, does it persist) to **predictive** science (does a structural property forecast a
future, out-of-sample outcome). This is a real methodological escalation, not "more MSRP experiments"
under a new name — see the three pre-registered hypotheses this lab opens with
(`labs/market_science/protocols/MSCI-001..003`).

## What this lab is explicitly NOT allowed to do

- **Validate anything by Sharpe ratio, backtest return, or any portfolio-level metric, ever.** This
  is an absolute prohibition, not a preference. If a Market Science finding looks tradeable, that
  observation gets handed to Alpha Engine as a *hypothesis* for their own, separately pre-registered
  pipeline — it is never validated here as if it were one.
  routes through Alpha Engine's own charter and pipeline, jointly registered if the finding
  originated here (see the Delivery/liquidity-gradient joint test precedent).
- **Report a windowed persistence or memory claim without the rolling-window artifact check and its
  Gen-8 caveat stated inline.** This is the exact mechanism this lab's own predecessor (MSRP) and
  Gen-6 caught five separate times project-wide. A sixth undisclosed occurrence would be a governance
  failure, not a new discovery.
- **Treat a single specification as confirmation.** Every claim needs replication across at least two
  independent measurement methods where feasible (the standing MSRP precedent: Gen-5's Shapley
  decomposition and MSRP's mutual-information analysis independently converged on the same feature
  without either being aware of the other's number — that is the standard to match, not exceed once
  and abandon).
- **Skip pre-registration because "this is just measurement."** Predictive hypotheses (does X forecast
  future Y) are discovery-stage science exactly like anything in Alpha Engine, and get the same
  power-disclosure and pre-registration discipline. Only pure descriptive replication of an already-
  frozen MSRP result may proceed without a fresh pre-registration, and even then must be logged.

## Validation standard

**Replication + permutation-null + synthetic-data control — statistical validity of a measurement,
never economic validity of a trade.**

1. **Replication**: an independent measurement method reaching the same conclusion, wherever two
   exist (information-theoretic and portfolio-attribution methods for cross-sectional claims;
   ACF/regime-conditional/state-lifetime methods for memory claims, per MSRP's own three-angle
   convergence precedent on `vol_52w` and `amihud_13w`).
2. **Permutation-null**: every predictive claim (Section "predictive escalation" below) must state
   the null it was tested against and the estimator's power to detect the pre-registered minimum
   effect, before the test is run (Amendment-002 made structural).
3. **Synthetic-data control**: for any claim about a windowed feature's temporal structure, a
   synthetic-noise version of the identical construction must be run alongside the real result (the
   Gen-8 G8-01B/G8-03 precedent) — the real result is only reportable as an excess over the
   mechanical/synthetic baseline, never as the raw statistic.

## Inherited governance (binding, not optional)

Same five items as every lab (pre-registration, power disclosure, rolling-window check with the
Gen-8 caveat, never-silently-rewrite-history, honest negative/inconclusive reporting) — see
`labs/alpha_engine/charter/CHARTER.md` for the shared text, not repeated here. Additionally inherited
specifically from MSRP: the **Rolling-Window Persistence Principle** as permanent law
(`MSRP_CHARTER.md`), the **structural-redundancy-vs-behavioral-coherence** distinction (orthogonal
properties, always reported separately), and MSRP's five Methodological Safeguards (measurement
before interpretation; disclose mid-experiment corrections transparently; preserve artefact-dominated
intermediate results, never delete; alternative-explanation notes for every positive finding;
report every claim's confidence level explicitly).

## Experiment ID convention

`MSCI-NNN`, assigned once, in order, by `research_os/experiment_registry.py`.
