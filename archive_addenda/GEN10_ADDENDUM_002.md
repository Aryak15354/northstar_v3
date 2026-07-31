# GEN-10 ADDENDUM 002 — Liquidity-conditional sizing is not established

```
Addendum:        GEN10_ADDENDUM_002
Issued:          2026-07-31
Author:          Aryak (Gen-10 Remediation Programme)
Addresses:       NSR-FIND-000043 (AEP-05)
Archive version: v1.0 (unmodified)
Evidence:        results/gen10/T0-02/T0-02_FINDINGS.md
Mechanism:       archive/GEN7_INTERFACE_RULE.md — addendum, not edit
```

## 1. The archived finding

**NSR-FIND-000043 (AEP-05)** — Economic Law, Moderate confidence, traces to AEP-PAPER-C:

> *"Liquidity-conditional sizing real (Sharpe +5%, vol −23%) but robustness-untested."*

The archive is **not** altered.

## 2. What Gen-10 found

**The effect is not established at all — not merely untested for robustness.** AEP Paper C reported
two point Sharpes with **no standard error and no significance test**. Supplying the test:

```
fixed    Sharpe 0.6918   vol 0.2492   annual return 17.24%
scaled   Sharpe 0.7271   vol 0.1923   annual return 13.98%

Sharpe difference  +0.0353   SE 0.0710   paired t = +0.50   p = 0.619
bootstrap 95% CI   [-0.156, +0.209]
MDE at 80% power   +0.1992  ->  the observed effect is 0.18x its own detection floor
return given up     3.26 %/yr
```

Three further problems, each independently disqualifying:

**(a) It is not a liquidity rule.** `PERSISTENT_REGIMES = {"NORMAL_UP", "STRESS"}` — the sizing keys
off the market-regime label. No measurement of liquidity persistence enters the decision. M-02's
finding is used to justify which labels to pick, not to compute anything.

**(b) The regime selection is wrong on its own terms.** De-gearing one regime at a time:

| de-gear only in… | Sharpe |
|---|---|
| **CRASH** | **0.8164** |
| **STRESS** | **0.7775** |
| RECOVERY | 0.6940 |
| STRONG_UP | 0.5941 |
| NORMAL_UP | 0.5030 |
| *the bundled rule* | *0.7271* |

Two single-regime rules beat the bundled rule, and one of them — STRESS — is a regime the rule
deliberately holds at **full** exposure.

**(c) It charges nothing for the de-gearing.** The construction uses gross `target_1w` with no
turnover cost for halving and restoring the book at every regime flip, and no cash yield on the
un-invested half. A cost-aware version is worse than what is shown.

## 3. It is also a rediscovery

"Regime-conditioned gross exposure timing beats static 1.0×" is **Gen-5 F11 / G5-05A**, already
**TERMINATED_BY_GATE** with oracle ceiling +0.1554 and realizable +0.1052 whose CI straddled the gate.
Paper C's +0.035 is a third of the realizable estimate that already failed. The programme also already
deploys a crash rule — A20 / G-05, "KEEP (mandatory)".

## 4. Paper C's other sub-questions

Also untested as archived, and supplied here:

| sub-question | archived | corrected |
|---|---|---|
| Q1 / Q4 execution cost | POSITIVE (modest), 3.90 vs 4.20 bps | **t = −1.75** — directional, not significant |
| Q2 universe | POSITIVE (modest), corr −0.119 | **not recomputed**; flagged NO-TEST, left open |

The consequence is practical: a standing recommendation to prefer liquidity-persistent names when a
trade can go either way would encode a t = −1.75 effect worth a quarter of a basis point.

## 5. Net effect on the archived record

| archived element | status after this addendum |
|---|---|
| NSR-FIND-000043 statement ("real but robustness-untested") | **superseded** — not established; t = 0.50, 0.18× its detection floor |
| its framing as a *liquidity* law | **superseded** — the rule keys off regime labels |
| Prototype 3 (Liquidity Persistence), Q3 sub-variant | **re-derived: REJECTED** |
| Paper C Q1/Q4 "POSITIVE (modest)" | **downgraded** to directional, not significant |
| Paper C Q2 | **flagged untested**, open |
| Paper C Sub-studies 2+3 (clean null) | **unchanged** — a bad SE does not manufacture a null |

**Live documents updated to match:** `results/AEP_PAPER_C/`, `results/AEP_PROTOTYPE_REGISTRY.md`,
`results/MASTER_HYPOTHESIS_AND_RESULTS_LEDGER_2026_07_28.md` §8d.

## 6. The general lesson, recorded separately

A verdict of ACCEPTED or POSITIVE should not be issuable from a point estimate. This is the
most common defect Gen-10 found in the AEP papers — more common than a *wrong* test — and it is
carried forward as a proposed constitutional rule rather than a one-off correction.
