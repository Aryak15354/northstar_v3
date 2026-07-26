# Northstar Institute — Status

**Purpose: if this session ended and a new one started with zero prior context, this document alone
should make the current state of the four-lab institute reconstructable.** Written 2026-07-26, the day
the "Gen-N" naming convention was retired and the four permanent labs were founded. Mirrors
`docs/RESEARCH_PROGRAMME_STATUS.md`'s own continuity convention for the prior Gen-N programme (still
the authoritative record of everything before this restructuring — nothing there was moved or
renamed).

---

## One paragraph

The Northstar Institute replaces "Gen-N" naming with four permanent labs — **Alpha Engine** (find new
return), **Market Science** (build theory, never portfolios), **Microstructure** (causal mechanism —
who and why, never what predicts), **Portfolio Engineering** (extract more from validated signals,
never discover new ones) — each with a concrete charter, and a shared `research_os/` providing
permanent per-lab experiment IDs, a four-outcome verdict schema, mandatory pre-registration with power
disclosure, and the Gen-8 rolling-window artifact check (with its own conservatism caveat). **Ten
experiments ran this session, all pre-registered before code, all closed with a verdict**: 2 REJECTED/
INCONCLUSIVE in Microstructure, 3 INCONCLUSIVE in Alpha Engine, 3 INCONCLUSIVE in Market Science, 3
VALIDATED in Portfolio Engineering. **Nothing in this entire session — or any prior Gen-N session — has
been committed to git.** That remains true as of this document; see "Before touching git" below.

## Start here

- **This document** for what happened this session.
- `docs/RESEARCH_PROGRAMME_STATUS.md` for everything before the restructuring (Gen-1 through Gen-9,
  ARP, AEP, MSRP) — still authoritative, not superseded.
- `docs/FIELD_REPORT_2026_07_26.md` (= root `RESEARCH_FIELD_REPORT.md`) for the synthesis of what this
  programme has learned about the market across all prior generations, written the same day as the
  restructuring, immediately before it.
- Each lab's `charter/CHARTER.md` for its objective, prohibitions, and validation standard.
- `research_os/RESEARCH_OS_README.md` for the shared infrastructure and its one disclosed known
  limitation (see below).
- `research_os/MASTER_EXPERIMENT_REGISTRY.csv` for the machine-readable record of all ten experiments.

---

## What each lab did this session

### Alpha Engine — 2 experiments, both INCONCLUSIVE (one substantively strong anyway)

- **ALPHA-001** — liquidity-decile IC gradient on a fresh 53-week post-lockbox window. Directionally
  consistent with G9-01 but only 40.9% power; INCONCLUSIVE by the pre-committed rule. ~135 weeks
  (≈2.6 years) would resolve it; the honest path is to let the window accrue.
- **ALPHA-002** (joint with Portfolio Engineering) — does Delivery's incremental IC survive
  controlling for liquidity? Formally INCONCLUSIVE against an overly conservative power heuristic, but
  the actual numbers (partial coefficient collapses to 2% of univariate magnitude, both effects highly
  significant) are one of the cleanest "one mechanism, not two" reads this programme has produced.
  **Read the findings doc, not just the verdict label, before using this.**
- Three explicit reasoned pauses recorded in `decision_log/DECISION_LOG.md`: no further
  representation-learning passes on this panel (needs a new data modality, not a new architecture); no
  further cross-asset transmission scans before Market Science resolves the market-beta-vs-
  transmission definitional question; no individual fast-turnover signal from the capital sweep treated
  as validated alone.

### Market Science Lab — 3 experiments, all INCONCLUSIVE

- **MSCI-001/002/003** — the first descriptive-to-predictive escalation of MSRP: does primitive
  stability, interaction complexity, or structural redundancy forecast future IC/crowding? All three
  underpowered at the pre-registered effect size (n_eff≈80 non-overlapping quarters vs. 347 needed).
  **MSCI-001 is flagged for a future session**: the relationship found is the *opposite* sign of the
  pre-registered hypothesis and nominally significant on both NW and permutation tests — a real
  exploratory lead, reported honestly rather than forced to match the hypothesis.
- One open paragraph recorded, not dismissed: whether detecting broad market-beta exposure would even
  count as answering Gen-7 Lab 5's original transmission question — a definitional question this lab
  owns, unscheduled, no experiment ID assigned yet because no pre-registration exists.

### Microstructure Lab — 2 experiments

- **MICRO-001** — modeled realistic exit-fill drag, replacing G8-12's crude bound with a real point
  estimate + CI. REJECTED (as material): −0.015%/yr differential, two orders of magnitude below the
  materiality bar. A real unit-conversion bug was caught and fixed mid-session; the false-start outputs
  are preserved, not deleted.
- **MICRO-002** — historical institutional-ownership coverage assessment. The 2010-2022 gap is total,
  not thin. Three sourcing options documented with a recommendation ordering. INCONCLUSIVE — **no
  acquisition was performed; the sourcing decision is the user's, not yet made.**

### Portfolio Engineering Lab — 3 experiments, all VALIDATED (with real caveats)

**This lab's first work across nine generations of this programme.** All three are sizing/execution
overlays on Sleeve-1 (Config-4+G-05, 80% of the frozen book) — no new predictive signal introduced.

- **PORT-001** — volatility-targeting leverage overlay. Sharpe +0.179 pre-lockbox (clears the +0.15
  bar), maxDD improves 14.9pp. **Caveat: underperforms in the lockbox-context window** — it levers up
  in any low-vol period regardless of sign, and the lockbox window has been low-vol and negative.
- **PORT-002** — drawdown-triggered de-gross overlay (a sizing rule; no options-pricing history deep
  enough exists to backtest a real protective put over 2005-2026). MaxDD improves 11.4pp (concentrated
  in the GFC window) for a 0.8pp CAGR cost.
- **PORT-003** — execution-schedule refinement at ₹2,500cr. 5-day staggered fills roughly halve total
  annual cost (948→529 bps/yr) vs. single-shot. Caveat: the cost model doesn't capture intraday adverse
  selection from working a multi-day order — read as a best-case estimate.
- Two real bugs were caught and fixed before any of these numbers were reported: a one-week look-ahead
  leak in the vol/drawdown trailing calculations (present in both PORT-001 and PORT-002), and a 2x
  overstatement of the short leg's notional in PORT-003's first pass. Both are documented in the
  findings doc with before/after numbers.
- **Scope limitation, stated plainly**: all three test Sleeve-1 alone; Sleeve-2 (sector rotation)'s own
  overlay behavior is untested this session.

---

## Open items for a future session

1. **MICRO-002 sourcing — live-verified, gap NOT resolved.** The user authorized BSE/NSE
   Regulation-31 archive scraping; a resumable, rate-limited, tested scraper exists at
   `scripts/microstructure/bse_nse_shareholding_scraper/`, and a real 2-request verification ran
   from this sandbox's Bash (the browsing tool itself stayed policy-blocked). Result: **NSE's
   endpoint works but only reaches ~2 years back** (a 2010-2022 request for RELIANCE returned 6
   records, all from late-2021+) — the same recent-only ceiling as Screener.in's free tier, a
   different vendor. **BSE's guessed endpoint is confirmed wrong** (redirects to a sales page); its
   real endpoint needs a live browser session this sandbox can't provide. See
   `MICRO-002_DATA_ACQUISITION.md` section 6. Two undone leads: parsing the XBRL filing archive each
   NSE record links to, and finding BSE's real endpoint outside this sandbox. The 2010-2022 gap
   remains open — do not treat it as resolved without re-running section 1's coverage diagnostic
   against real landed data.
2. **MSCI-001's reversed-sign finding** — a real, exploratory, statistically live-looking lead
   (stability predicts *lower*, not higher, future IC) worth its own fresh pre-registration, not an
   extension of this session's contract.
3. **Market Science's market-beta-vs-transmission definitional question** — needs a pre-registered
   answer before any future cross-asset transmission scan is legitimate.
4. **`research_os.power_precheck`'s known limitation** (documented in `RESEARCH_OS_README.md`): its
   correlation-power formula understates power for designs that test the mean of an already-aggregated
   weekly statistic (used by `ALPHA-001`, `ALPHA-002`, `MSCI-001..003`). A dedicated NW-mean-test power
   calculator, modeled on `G8-09`'s own `se_sharpe` approach, would let these close more precisely
   instead of carrying a disclosed caveat in every findings doc.
5. **Portfolio Engineering's Sleeve-2 gap** — none of PORT-001/002/003 has been tested against the
   sector-rotation sleeve or the combined 80/20 book; only Sleeve-1 was in scope this session.
6. **ALPHA-002's implication for capital allocation** — cross-referenced in Portfolio Engineering's
   decision log, not yet acted on: a future book should not size Delivery and the liquidity tilt as
   independent ₹5–10cr sleeves.

## Before touching git

**Nothing in this session, or in any prior Gen-N session, has been committed.** Per standing repo
convention, this restructuring — new lab directories, charters, `research_os/`, ten experiments' worth
of protocols/results/decision logs — is exactly the kind of change that should be a deliberate,
reviewed commit rather than an incidental one. No git command has been run this session; none should
be without explicit confirmation first.
