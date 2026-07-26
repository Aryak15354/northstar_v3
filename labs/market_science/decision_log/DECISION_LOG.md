# Market Science Lab — Decision Log

Append-only. Entries are added, never edited in place except to update a "status" line when a paused
item is later reopened (with a link to the reopening experiment).

---

## 2026-07-26 — Experiments closed this session

- **MSCI-001/002/003** (`labs/market_science/results/MSCI-001-002-003/FINDINGS.md`) — the first
  descriptive-to-predictive escalation of MSRP: three pre-registered forecasting hypotheses (does
  primitive stability, interaction complexity, or structural redundancy predict future IC or
  crowding). All three closed **INCONCLUSIVE** on power grounds (n_eff≈80 non-overlapping quarters
  vs. 347 needed at the pre-registered effect size) — not evidence against any of the three. MSCI-001
  is flagged for a future session: the observed relationship is the *opposite* sign of the
  pre-registered hypothesis and nominally significant on both NW and permutation tests, an
  exploratory observation worth a dedicated fresh pre-registration, not a result to act on now.

---

## 2026-07-26 (same day) — MSCI-004 closed

Follow-up to MSCI-001's reversed-sign flag, using the OTHER operationalization MSCI-001's own
pre-registration named but never tested (volatility-regime-classification stability, not rank
stability). Result: **does not replicate** — r=+0.069, NW p=0.44, perm p=0.51, wrong-signed vs. the
primary hypothesis and far from significant. A useful, honest negative: MSCI-001's surprise looks
specific to `res_mom_52w_ex4w`'s own rank-stability construction, not a general "quiet markets carry
less information" regularity. Closed **INCONCLUSIVE** (also underpowered by the standard gate, but
the point estimate itself gives no reason to prioritize further data accrual here the way MSCI-001's
own result does).

## 2026-07-26 — Explicit reasoned pauses (Phase 3, Northstar Institute restructuring)

### PAUSED — No further representation-learning passes on this panel

Cross-referenced from `labs/alpha_engine/decision_log/DECISION_LOG.md`, which carries the full
reasoning (Gen-6 Paper 1 + Gen-8 G8-01, both closed with no positive evidence, R0/R0B caught a
construction artifact in an earlier apparent positive). From this lab's own charter angle: MSRP's
entire descriptive programme (Phase 1/2, `PHASE1_SYNTHESIS_FROZEN.md`) was built specifically on
**interpretable, hand-specified primitives** precisely because the representation-learning
alternative failed to outperform them — this is not an oversight to revisit but the documented reason
this lab's information hierarchy looks the way it does. Reopening criteria are identical to Alpha
Engine's: a genuinely different data modality, not another pass over the same weekly panel.

### PAUSED — The market-beta vs. transmission question (Gen-7 Lab 5), one open paragraph

This lab is the natural owner of resolving *what a "transmission" claim actually means* when a
cross-asset scan hits nearly every sector cell equally — that is a definitional/theoretical question
about how to distinguish broad market-beta co-movement from a genuine carrier-specific channel, not a
question answered by running more data through the same design. **This is flagged as a real,
un-scheduled open item**, not dismissed: a rigorous answer would need to specify, in advance, what a
transmission-consistent pattern of sector heterogeneity would look like (e.g., transmission strength
correlated with a sector's actual economic exposure to the carrier, vs. uniform loading consistent
with pure beta) and pre-register that distinction before the next scan runs. No experiment number is
assigned yet because no pre-registration exists — this is the honest paragraph the restructuring plan
asked for, not a placeholder for future avoidance.

### Standing charter reminder (not a pause, a standing rule)

This lab's charter absolutely forbids Sharpe-based validation of any finding, including anything that
emerges from resolving the two items above. A definitional resolution of the market-beta question, or
any future representation-learning result on a genuinely new data modality, is validated as a
forecasting/replication claim on this lab's own terms — never handed to Alpha Engine pre-validated as
a trading signal.
