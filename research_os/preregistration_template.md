<!--
PREREGISTRATION TEMPLATE — Northstar Research Institute

Fill this out and commit it BEFORE any result-producing code runs. This is not a formality — per
Amendment-002 (Gen-7) made structural, the power-disclosure section below is a HARD GATE:
`research_os/power_precheck.py` refuses to let an experiment proceed to discovery mode without it
being logged first, and `research_os/verdict_schema.py` refuses to let VALIDATED/REJECTED verdicts
close without a stated power figure.

Copy this file to `labs/{lab}/protocols/{EXPERIMENT_ID}_{short_name}.md`, fill in every section, THEN
call `research_os.experiment_registry.register_experiment(...)` to get the permanent ID, then rename
the file to include that ID if it wasn't already known.

Delete this comment block before committing the filled-out protocol.
-->

# {EXPERIMENT_ID} — {Short Title}

```
Version:            v1.0
Status:             Draft | Frozen
Freeze Date:        YYYY-MM-DD (blank if Draft)
Owner:              {name}
Lab:                {alpha_engine | market_science | microstructure | portfolio_engineering}
Depends On:         {documents this experiment requires to be valid — cite specific files, not
                    generic references}
Related Registries: research_os/MASTER_EXPERIMENT_REGISTRY.csv
```

## 1. Defect / prior-result applicability check (if re-testing anything)

Before re-running any prior result: did the specific defect/limitation actually apply to it? Check
and log the answer either way — "it probably did" is not a check. If this is a wholly new question,
state that explicitly instead.

## 2. Research question

One sentence, falsifiable. State explicitly why this is not already answered by an existing frozen
result — cite the specific document and explain the difference, per this repository's own standing
discipline against re-litigating closed questions without new evidence.

## 3. Hypotheses

State each hypothesis with its explicit null. Number them (H-{ID}-1, H-{ID}-2, ...).

## 4. Pre-registered specification — ONE test per hypothesis

Per Standing Rule 3 (inherited from Gen-8): the single most-motivated specification (one lag, one
window, one parameterization), chosen from domain reasoning or a prior generation's finding, **not**
selected after seeing results. State the reasoning here, before any code runs. A scan across many
specifications is a separate, explicitly-labelled EXPLORATORY analysis that cannot promote anything.

## 5. Power disclosure — MANDATORY, computed before execution

Call `research_os.power_precheck.power_precheck(...)` (or `simulation_power` for a model class with
no closed form) and paste its output here:

- Sample size / test design:
- Meaningful effect size (stated in advance, tied to a real economic or scientific bar — e.g. Gen-5's
  +0.15 realizable Sharpe, or Delivery's certified +0.033 IC as a materiality floor):
- Minimum detectable effect at 80% power:
- Power at the meaningful effect:
- **If underpowered:** is `--i-understand-this-is-underpowered` being used? If so, the outcome is
  fixed in advance as INCONCLUSIVE, never VALIDATED/REJECTED, regardless of what the numbers show.

## 6. Validation design

If this experiment needs an out-of-sample holdout, call
`research_os.power_precheck.recommend_validation_design(...)` and paste its recommendation here.
State explicitly whether the holdout/window has been inspected by any prior experiment — if it has,
this is a re-analysis, not a fresh test, and carries less evidential weight (per the Gen-8 G8-02
precedent).

## 7. Promotion / rejection gates

Pre-registered thresholds, stated numerically, before any result is seen. Include, where applicable:
statistical (valid p-value, multiplicity-corrected), economic (Universal Oracle Ladder, Alpha Engine
only), robustness (survivorship/tradeability/multiplicity, per the lab's charter), and the
rolling-window artifact check (`research_os.rolling_window_artifact_check`) for any windowed feature
involved in a persistence/memory/autocorrelation claim — **state the Gen-8 caveat inline** (differencing
is a conservative one-directional screen, not a clean discriminator).

## 8. Exclusions

What this experiment explicitly does NOT test. State the boundary precisely enough that a future
session cannot misread a narrow result as a broad one.

## 9. Anticipated failure modes

What could go wrong with this specific design, and what check catches each one.

## 10. Outcome classification

State in advance which of the four schema verdicts (`research_os.verdict_schema.Verdict`) would apply
under each plausible result. This is not the actual verdict — it's a pre-committed decision rule so
the eventual verdict cannot be chosen after the fact to fit the numbers.
