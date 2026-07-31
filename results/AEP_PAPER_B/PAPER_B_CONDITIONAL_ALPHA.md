> ## ⚠ CORRECTION — Sub-study 2 (2026-07-31, Gen-10 T0-01 / T1-05″)
>
> **Sub-study 2's two headline results swap places, and both then close.** The t-statistics below
> pool ~62,000 stock-weeks as independent observations. They are not: forward returns over *h* weeks
> overlap by construction, and stocks within a week share a market factor. The effective sample is
> ~1,030 dates.
>
> | role | archived | corrected (date-clustered NW) |
> |---|---|---|
> | **2b "Warns"** | **CONFIRMED**, t = 2.25 / 2.03 / 2.07 | **RETIRED** — t = +0.57 at best, sign flips across horizons, **all four lockbox horizons negative** |
> | **2a "Confirms"** | NOT CONFIRMED (near-miss), t = 1.97–1.91 | the only coherent role — t = **+2.52** at 4w, monotone, lockbox-replicated in direction — but **fails the pre-registered multiplicity correction and is now closed** (T1-05″: 8 further tests using 33% and 100% of the cross-section, best t = 1.88) |
>
> **Net: no role for `consistency_mom_26w` is confirmed.** 2b retired, 2c/2d rejected, 2a closed as a
> documented near-effect. Prototype 2 re-derived accordingly.
>
> Sub-study 1 is **unaffected** — it counts alternate-split replications rather than using a pooled t,
> and its rejection stands.
>
> Evidence: `results/gen10/T0-01/`, `results/gen10/T1-05/`. Archive addendum:
> `archive_addenda/GEN10_ADDENDUM_001.md` (NSR-FIND-000042).
> The original text below is left intact — it records what was concluded on the statistic then in use.

---

# Paper B — Conditional Alpha: FINDINGS (FROZEN v1.0)

Per `docs/aep_protocols/PAPER-B_RESEARCH_CONTRACT.md`.

## Sub-study 1 — Conditional Trend Persistence: REJECTED for engineering (does not proceed to Phase D)

**Phase A (Replication): PASS.** Reproduces M-04 exactly (Low-Vol=M4, High-Vol=M2) — confirmed after
catching and fixing a real bug in the first script version (the split threshold was computed on the
target-reindexed series instead of the full conditioning series; fixed, re-verified against M-04's exact
output before trusting anything downstream — the correctness-gate-first discipline caught this before it
propagated).

**Phase B (Sensitivity): FAILS the pre-registered robustness bar.** At the median (50%) split, the
effect replicates (Low=M4, High=M2). But at 2 of 5 alternate splits (33%, 40%), the modulation
**disappears entirely** (Low=High=M2) — meeting the pre-registered fragility criterion ("fails at 2 or
more of the 4 alternative splits"). Only 3/5 alternates show any modulation at all, and even those don't
consistently reproduce the specific M4-vs-M2 pattern.

**Phase C (Definition robustness): FAILS the pre-registered bar.** Direction replicates in only 2 of 4
alternate volatility definitions (`beta_104w`, the volatility-family PC1) — required ≥3/4. `vol_13w` and
`idio_vol_13w` both fail to replicate the direction.

**Verdict: the specific M-04 finding stands as a valid, correctly-reported MSRP result at its original
test specification — but does NOT clear the bar this paper's own contract set for treating it as a
general, robust "volatility regime modulates trend memory" phenomenon.** Per the pre-registered failure
criterion, Sub-study 1 does **not** proceed to Phase D (engineering a sizing rule). This is a disciplined,
informative negative result, not a failure of the research process — the whole point of Phases B/C was to
distinguish a robust phenomenon from a single-specification artifact, and they did their job.

**Consequence for AEP more broadly:** the "low-volatility momentum sizing" prototype that motivated much
of the AEP restructuring is **not currently validated for engineering**. This does not retroactively
invalidate M-04 as an MSRP finding (it remains accepted at its own specification), but it does mean AEP
should not build a position-sizing rule on it without either (a) a materially different, better-motivated
volatility-state construction, or (b) accepting a much narrower, specification-tied claim than originally
hoped.

## Sub-study 2 — Conditional Information Activation: PARTIALLY informative, does not cleanly resolve the
4 candidate roles

**Test (a) Confirms** (forward return, High-Trend × High-Consistency vs. High-Trend × Low-Consistency):
grows with horizon, nearly clears significance (t=1.97 at 8wk, 1.91 at 13wk) but does not clear the
pre-registered |t|≥2 bar.

**Test (b) Warns/independent-flag** (forward return, Low-Trend × High-Consistency vs. Low-Trend ×
Low-Consistency): **clears the bar** (t=2.25 at 4wk, 2.03 at 8wk, 2.07 at 13wk).

**The honest, non-obvious finding: (a) and (b) show comparable effect magnitudes** (0.18–0.44% for
Confirms, 0.25–0.42% for Warns) — `consistency_mom_26w` predicts forward returns at a roughly similar
strength **regardless of whether trend is High or Low.** This is in real tension with I-05/M-05's "dead
standalone, alive only conditional on trend" characterization — that framing came from an
incremental-mutual-information/memory-conditioning methodology, and this paper's direct return-spread
test does not cleanly reproduce the same conditional-only story. **Flagged explicitly as an unresolved
discrepancy between methodologies, not silently resolved either way** — I-05/M-05 measured *information
content* (MI, autocorrelation), this test measures *realized return spread*, and the two need not agree
perfectly even when both are correctly computed.

**Test (c) Delays**: cross-correlation between trend and consistency is stable and negative (~−0.18) at
every lag from −4 to +4 weeks, with no directional asymmetry. **No support for a lead/lag "Delays" role.**

**Test (d) Accelerates-exits**: not significant (t=0.79, n=4,512 dropped-consistency observations).
**No support.**

**Verdict: none of the four pre-registered candidate roles is cleanly confirmed in isolation.** The
closest to a clean signal is that `consistency_mom_26w` carries a real, roughly trend-state-independent
positive relationship with 8–13-week forward returns — which is itself a genuinely new characterization,
different from both "dead standalone" (I-01/I-02) and "purely conditional" (I-05/M-05). **This should be
carried into the eventual AEP/MSRP synthesis as an open methodological question** (do incremental-MI-based
and direct-return-spread-based characterizations of the same primitive need to agree, and if not, which
should be trusted for engineering purposes) rather than papered over.

## Combined Paper B conclusion
**Neither sub-study produces a directly engineerable prototype at this pass.** Sub-study 1 is a clean
negative result (fails its own robustness bars). Sub-study 2 produces a real but incompletely-resolved
picture — real information exists, but its precise conditional structure remains unsettled between two
different measurement approaches. Per `AEP_MASTER_RESEARCH_PLAN.md`'s promotion criteria, both are
classified **Modified** (not Accepted, not fully Rejected): the underlying MSRP findings (M-04, I-05,
M-05) remain valid and accepted at their own original specifications; the *engineering* extrapolation
this paper attempted does not clear the higher bar this paper's contract set for it.

## What Paper C and Paper E should take from this
Paper E (Confidence Engine) should NOT assume Paper B supplies a validated volatility-sizing rule or a
resolved consistency-role — if Paper E proceeds, it must either use the narrower, specification-tied M-04
finding explicitly caveated, or treat both Paper B sub-studies as open inputs rather than settled
components. This is exactly the kind of dependency-chain caution `AEP_DEPENDENCY_MAP.md` was built to
surface.

---
**Paper B is FROZEN as of this document. Verdict: MODIFIED (both sub-studies) — real findings, real
methodology, does not clear the bar for engineering promotion at this pass.**
