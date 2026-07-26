# MSCI-004 — Volatility-Regime Stability and Future IC (the second operationalization from MSCI-001)

```
Version:            v1.0
Status:             Frozen (pre-registration — written before any result-producing code runs)
Freeze Date:        2026-07-26
Owner:              Aryak
Lab:                market_science
Depends On:         labs/market_science/results/MSCI-001-002-003/FINDINGS.md (the reversed-sign
                    flag this follows up on, with a genuinely different predictor construction —
                    not a re-fit of the same evidence)
```

## Why this is a fresh experiment, not a re-fit

MSCI-001's own pre-registration named **two** candidate operationalizations of "primitive stability":
"(e.g. how consistently `res_mom_52w_ex4w` **or the volatility regime** classifies across rolling
sub-periods)." Only the first was tested. MSCI-001 found the *opposite* sign from its pre-registered
hypothesis — higher rank-stability predicted *lower*, not higher, forward IC — and closed
INCONCLUSIVE only because of a formal power gate, not because the effect wasn't real (NW p=0.002,
permutation p=0.031). **This experiment tests the second, never-inspected operationalization on an
independent construction, sharing only the outcome variable (which was not itself the source of the
reversed-sign surprise).** This is a replication attempt via a different method, exactly what this
lab's charter requires before treating a single-specification result as confirmed — not a re-test of
the same evidence with a flipped label.

## Research question

Does the trailing stability of the market's own volatility-regime classification (CRASH / STRESS /
NORMAL_UP / STRONG_UP / RECOVERY, per `run_g02_regime.py`'s own PIT regime classifier — reused
verbatim, not rebuilt) predict the forward realized IC of `res_mom_52w_ex4w`?

## Pre-registered specification

**Predictor**: trailing 52-week regime stability = `1 - (fraction of week-over-week regime label
changes in the trailing 52 weeks)`, computed strictly from data through week *t* (the regime
classifier itself is already PIT-safe, built from realized trailing return/vol only).

**Outcome**: forward-realized 13-week mean cross-sectional Spearman IC of `res_mom_52w_ex4w` vs.
`target_1w` — identical construction to MSCI-001's own outcome series (reusing this series is not
reusing "evidence" in the sense that matters: the outcome was never the object of MSCI-001's
surprising finding, the *predictor* was).

**H-MSCI-004-1 (primary, informed by MSCI-001)**: higher trailing regime-stability predicts *lower*
forward IC of `res_mom_52w_ex4w` — extending MSCI-001's "quiet periods carry less resolved
information" reading to an independent construction. *H₀: no correlation.*

## Validation (identical methodology to MSCI-001/002/003)

Newey-West HAC test + circular block-bootstrap permutation null (`research_os.valid_pvalue`) +
power precheck (`research_os.power_precheck`, `n_eff` = non-overlapping 13-week blocks, same
convention as MSCI-001/002/003) + `research_os.rolling_window_artifact_check` on the predictor series
(window=52, Gen-8 caveat stated inline) + **no Sharpe-based validation of any kind**, per this lab's
absolute charter prohibition.

## Exclusions

- Single pre-registered specification (52-week window, 13-week horizon) — no scan across windows.
- No portfolio or economic claim — a positive result here is handed to Alpha Engine as a fresh
  hypothesis if it clears validation, never validated as tradeable by this lab.
- Does not reopen MSCI-001 itself — that closure stands regardless of this result.

## Outcome classification

Same four-verdict schema as every other experiment this session. An underpowered result closes
INCONCLUSIVE regardless of point estimate direction, per this programme's standing discipline.
