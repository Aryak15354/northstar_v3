# T1-04a — DS Delivery Cluster Through the Economic Gate. Findings

```
Version:      v1.0
Status:       Frozen
Freeze Date:  2026-07-31
Owner:        Aryak
Depends On:   results/gen10/T0-02 (battery verified clean), results/gen10/T0-03 (delivery
              verified free of the composition artifact), GEN10_REMEDIATION_CHARTER.md s4/T1-04a
Artifacts:    t1_04a_stage1_data.json, t1_04a_stage1b_data.json
Scripts:      scripts/gen10/t1_04a_ds_delivery_stage1.py, t1_04a_stage1b_redundancy.py
```

**Outcome: the remediation plan's highest-priority cluster contains exactly one signal, and it is
already in the book.** Nine catalogued delivery items reduce to one duplicate, five that die at the
first out-of-sample split they have ever faced, and three survivors that are the same signal measured
three ways — the strongest of which is `delivery_pct_4w_avg`, i.e. G2-E03b, promoted in 2026.
**Stages 2–4 are not run: there is no new candidate to gate.**

---

## 1. What was tested and why the split matters

All 28 deep-search items were evaluated on the full sample. Their manifests carry
`"lockbox_used": false`, and `deepsearch.fast_ic` runs across every date. The one item that later
received a genuine split — DS-F3-04 — collapsed from t = −4.4 to t = −0.06. This is the first
out-of-sample evaluation the delivery cluster has ever had.

Windows, fixed before any result was read (delivery data begins 2020-01-03):

| window | span | weeks |
|---|---|---|
| DISCOVERY | 2020-01-03 … 2023-12-29 | 209 |
| OOS | 2024-01-05 … 2025-07-04 | 79 |
| LOCKBOX | 2025-07-11 … 2026-06-26 | 51 |

Signal specs were lifted verbatim from `scripts/gen23/deepsearch.py` so the evaluation window is the
only thing that changes. **DS-U-04 was dropped before running** — T0-02 verified it is byte-identical
to DS-F5-01 (`rel_deliv_sector`, IC equal to seven decimal places). Nine catalogued items are eight
distinct tests.

## 2. Stage 1 — first out-of-sample split

| ID | spec | archived t | full t | DISC t | **OOS t** | LOCK t | verdict |
|---|---|---|---|---|---|---|---|
| DS-F1-01 | `ix_deliv_mom` | −1.88 | −1.87 | −1.31 | **−1.28** | −0.56 | KILL |
| DS-F1-04 | `ix_deliv_breakout` | −2.95 | −2.87 | −2.24 | **−1.85** | −0.78 | KILL |
| DS-F1-05 | `dv_deliv_price` | +4.21 | +4.17 | +2.97 | **+2.92** | +1.44 | survives |
| DS-F1-06 | `pa_deliv_jump` | +3.46 | +3.50 | +2.93 | **+0.42** | +3.07 | KILL |
| DS-F3-01 | `delivery_pct_4w_avg` (failure) | +2.34 | +2.34 | +1.57 | **+1.91** | +0.66 | KILL |
| DS-F3-02 | `delivery_pct_z52` (failure) | +3.02 | +3.01 | +2.03 | **+1.76** | +1.61 | KILL |
| DS-F5-01 | `rel_deliv_sector` | +4.93 | +4.88 | +3.51 | **+3.92** | +1.20 | survives |
| DS-U-02 | `delivery_pct_4w_avg` | +4.06 | +4.05 | +2.88 | **+3.07** | +1.10 | survives |

**3 of 8 survive**, and all three are BY-clean at q=0.05 across the deduped cluster
(p = 0.0046 / 0.0002 / 0.0030).

Two things worth noting:

- **The gate has a working control.** DS-U-02 *is* G2-E03b, already independently certified and
  promoted through ARP. It survives. A gate that killed the known-good signal would be broken; this
  one does not.
- **Every conditional and interaction construction dies.** All four F1 interaction terms and both F3
  "which momentum longs succeed" tests fail. DS-F1-06 is the clearest illustration of why the split
  was needed: discovery t = +2.93, OOS t = +0.42, lockbox t = +3.07 — an unstable signal that the
  full-sample number (+3.50) presented as strong.

## 3. Stage 1b — the three survivors are one signal

All three are built from `delivery_pct_4w_avg`, so redundancy was tested before spending Stages 2–4.

**Pairwise per-date Spearman (OOS window):**

| pair | ρ |
|---|---|
| DS-U-02 ~ DS-F5-01 | **+0.924** |
| DS-U-02 ~ DS-F1-05 | +0.777 |
| DS-F5-01 ~ DS-F1-05 | +0.722 |

**Incremental IC** — orthogonalise each candidate against the incumbent per date, in rank space, and
re-test:

| candidate | raw OOS t | residual t after removing DS-U-02 | t retained | verdict |
|---|---|---|---|---|
| DS-F5-01 | +3.92 | **+0.61** | 16% | REDUNDANT |
| DS-F1-05 | +2.92 | **+0.27** | 9% | REDUNDANT |

**Reverse check** — is the incumbent merely a worse version of the challenger? DS-U-02's t falls from
+3.07 to +1.44 once DS-F5-01 is removed. Neither cleanly subsumes the other, which is the signature of
one underlying signal rather than two dimensions.

**Stability** — repeating the orthogonalisation on the full 339-week window gives residual
t = +1.90 (DS-F5-01) and +1.01 (DS-F1-05). Neither clears 2 on any window.

This is Gen-5 F01 again: individually significant, jointly redundant. There the momentum composite's
four members each carried Shapley 19–31% with leave-one-out ≈ 0. Here three delivery constructions
each carry OOS t ≈ 3–4 with incremental t ≈ 0.3–0.6.

## 4. Why Stages 2–4 were not run

The charter's Stage 2–4 sequence exists to decide whether a **new** statistical signal is
economically deployable. After Stage 1b there is no new signal: the surviving information is
`delivery_pct_4w_avg`, which has already been through a capacity ladder (ARP dossier, ₹5L–₹500cr),
an overlay test against the real certified book (G8-09), and ten adversarial certification tests.
Running an oracle ceiling on it would re-derive results that already exist.

Running Stages 2–4 anyway would not be rigour, it would be a fourth measurement of a signal whose
economics are the best-characterised in the programme.

## 5. Findings

**G10-F11 — the DS delivery cluster contains one signal, already deployed.** Nine catalogued items →
one exact duplicate (DS-U-04 ≡ DS-F5-01) → five killed at the first OOS split → three survivors with
pairwise ρ of 0.72–0.92 and incremental t of 0.27–0.61 against the incumbent. The remediation plan's
"highest priority, ~15 statistically real signals" cluster yields no new deployable alpha.

**G10-F12 — full-sample deep-search t-statistics do not survive an out-of-sample split.** 5 of 8
delivery items fail, including two (DS-F1-04 at −2.95, DS-F1-06 at +3.46) that looked comfortably
significant full-sample. Combined with DS-F3-04's earlier collapse, the base rate for DS-battery
items surviving their first genuine split is now 3 of 9 — and all three of those are one signal.
**RESEARCH_SIGNAL, as issued by the deep search, does not predict out-of-sample survival.**

**G10-F13 — delivery's information is unconditional.** Every conditional form was killed: interaction
with momentum, with breakouts, with volume surges, and both "which momentum longs succeed" framings.
The signal works as a standalone cross-sectional ranking and adds nothing as a conditioner. This is
consistent with G8-09's finding that the overlay adds nothing to a book that already holds correlated
names.

## 6. Consequences for the remediation plan

- **Plan item 2.4's delivery cluster is closed with a negative result.** The plan ranked it "highest
  priority… most likely to actually convert." It did not convert, and the reason is redundancy the
  plan half-anticipated ("check for redundancy before treating them as two signals") but scoped only
  to the F5-01/U-04 pair. The redundancy is cluster-wide.
- **The plan's sequencing advice still paid off.** It recommended taking this cluster through all four
  stages first and using what was learned to make the others faster. What was learned: run the
  redundancy check immediately after Stage 1 and before Stages 2–4, on every cluster. That is now
  standing procedure for T1-09.
- **T1-09 (momentum-quality and cross-factor clusters) inherits a strong prior.** Those clusters are
  built from `mom_60d_cs_z` and `vol_60d`, both of which are broad-coverage signals — so unlike
  delivery they are *exposed* to the T0-03 composition artifact and must be corrected for it before
  Stage 1, not after.

## 7. Threats to validity

- **The OOS window is 79 weeks and the lockbox 51.** Survivors' lockbox t-statistics (1.10–1.44) are
  not confirmations; that window's minimum detectable effect is well above the effects being sought,
  the same limitation quantified in T0-01 §3. Stage 1's kill decisions rest on the OOS window, which
  is where the pre-registered rule placed them.
- **A 2020-only history means one market era.** Every delivery result in the programme carries this,
  and it is why five kills here should be read as "did not replicate in 2024–25" rather than "does not
  exist".
- **Orthogonalisation is per-date and linear in rank space**, matching the Spearman IC used
  throughout. A non-linear relationship between candidate and incumbent would be partly missed; the
  0.72–0.92 raw rank correlations make that unlikely to change the conclusion.
- **DS-F3-01/F3-02 were evaluated at the top-quintile momentum cut used by `deepsearch.failure_ic`.**
  A different cut is untested. Both fail with OOS t of 1.91 and 1.76, close enough to the bar that a
  friendlier cut might cross it — which is exactly why the cut was fixed in advance.
