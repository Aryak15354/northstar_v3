# CHARTER — Microstructure Lab (Programme C)

```
Version:            v1.0
Status:             Frozen
Freeze Date:        2026-07-26
Owner:              Aryak
Depends On:         docs/FIELD_REPORT_2026_07_26.md, results/gen8/G8-12/G8-12_FINDINGS.md (the
                    truncation bound this lab's first workstream tightens),
                    results/gen8/G9-01/G9-01_FINDINGS.md, results/gen8/G9-02/G9-02_FINDINGS.md
Related Registries: research_os/MASTER_EXPERIMENT_REGISTRY.csv (MICRO-NNN)
```

## Objective

**Explain the causal mechanism behind a phenomenon another lab has already found — "who, and why,"
never "what predicts."** This lab does not discover new predictive signals. It exists because two
findings this session (the liquidity gradient, G9-01/F&O mislabeling; the delisting-truncation bias,
G8-12) each raised a mechanism question — *why* does receptivity vary with liquidity; *what actually
happens* to a name's price/liquidity as it approaches delisting — that neither Alpha Engine's
discovery pipeline nor Market Science's structural-measurement pipeline is built to answer.

## Scope

Causal-inference questions about *why* an already-established empirical pattern exists: institutional
participation, execution mechanics, delisting/illiquidity exit dynamics, market-maker/arbitrageur
behavior, and any other question of mechanism rather than prediction. Candidate methods: instrumental
variables, difference-in-differences, synthetic control, matched-sample comparison, direct
microstructure simulation (order-fill modeling).

## What this lab is explicitly NOT allowed to do

- **Answer "what predicts returns."** That question belongs to Alpha Engine. If a mechanism study
  incidentally surfaces a candidate predictive signal, it is handed to Alpha Engine as a fresh
  pre-registered hypothesis — never validated or reported as a trading finding from this lab.
- **Claim causal identification from a correlational design.** A regression showing X and Y move
  together is not this lab's standard of evidence — see G9-02's own experience this session, where a
  correlational join collapsed to an unrepresentative 112-week window and the honest conclusion was
  "unresolved," not "ownership explains it." This lab exists specifically to do better than that, and
  must use an actual identification strategy (instrument, natural experiment, matched control) or
  report the question as still open.
- **Simulate around a real data gap.** If a mechanism question requires data this repository does not
  have (e.g., historical institutional ownership 2010–2022, per MICRO-002), the acquisition gap is
  reported honestly — real coverage achieved, real coverage missing — never papered over with an
  assumption dressed as a measurement.
- **Treat a bounding assumption as a point estimate.** MICRO-001 exists precisely because a crude
  bound (0 to −2.29%/yr, G8-12) is not a mechanism explanation — replacing it with a *modeled* point
  estimate and confidence interval, stating the assumptions that went into it explicitly, is the
  minimum bar for this lab's first deliverable to count as microstructure work rather than a relabeled
  bound.

## Validation standard

**Causal-inference standard, not predictive or portfolio standard.**

1. State the causal question and the identification strategy *before* looking at data (instrument,
   discontinuity, matched control, or an explicit natural-experiment argument for why a correlational
   design is defensible in this specific case).
2. State what would falsify the causal claim, not just what would fail to detect an association.
3. Report the mechanism finding independent of any economic implication — a real, well-identified
   mechanism with zero tradeable consequence is a complete, valid, citable outcome (this lab's
   equivalent of Market Science's ban on Sharpe-based validation).
4. Where genuine causal identification is not achievable with available data, say so explicitly and
   report the question as INCONCLUSIVE or state the specific acquisition/design gap that would
   resolve it — do not report a correlational finding dressed as a causal one.

## Inherited governance (binding, not optional)

Same five items as every lab (pre-registration, power disclosure, rolling-window check with the
Gen-8 caveat, never-silently-rewrite-history, honest negative/inconclusive reporting) — shared text
in `labs/alpha_engine/charter/CHARTER.md`.

## Experiment ID convention

`MICRO-NNN`, assigned once, in order, by `research_os/experiment_registry.py`.
