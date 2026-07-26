# Alpha Engine — Decision Log

Append-only. Entries are added, never edited in place except to update a "status" line when a paused
item is later reopened (with a link to the reopening experiment) or a registry cross-reference is
added.

---

## 2026-07-26 — Experiments closed this session

- **ALPHA-001** (`labs/alpha_engine/results/ALPHA-001/FINDINGS.md`) — liquidity-decile IC gradient
  tested on the fresh 53-week post-lockbox window. Directionally consistent with G9-01 but the design
  has only 40.9% power; closed **INCONCLUSIVE** by the pre-committed rule. G9-01 itself stands
  unaffected (810 weeks, p=0.00027).
- **ALPHA-002** (`labs/alpha_engine/results/ALPHA-002/FINDINGS.md`) — joint with Portfolio
  Engineering. Tested whether Delivery's incremental IC survives controlling for the liquidity
  gradient. Closed **INCONCLUSIVE** by the pre-registered power gate, but the underlying numbers are
  one of the clearest "these are one mechanism, not two" results this programme has produced (partial
  coefficient collapses to 2% of its univariate magnitude). Read the findings doc in full before
  treating the INCONCLUSIVE label as "no effect" — see its "honest tension" section.

---

## 2026-07-26 — Explicit reasoned pauses (Phase 3, Northstar Institute restructuring)

These are not silent omissions. Each states what would have to be true for a future session to
reopen it, per this lab's charter (`labs/alpha_engine/charter/CHARTER.md`): *"reopening a permanently
retired direction without new evidence"* is itself a listed prohibition.

### PAUSED — No further representation-learning passes on this panel

Gen-6's Paper 1 (`docs/GEN6_DECISION_LOG.md`, `project_gen6_representation_learning_2026_07_24`
memory) closed GRU/LSTM/autoencoder representation learning on PANEL-A/B with no positive evidence
over the existing Gen-5 feature ontology — R0/R0B specifically caught a rolling-window construction
artifact that had inflated an earlier positive read. Gen-8's own G8-01 re-run reached the same
conclusion independently. **This is now the third closure of the same direction on the same
underlying panel.**

**What would reopen it:** a genuinely different data modality — not another architecture, another
window length, or another training objective run against the same weekly OHLCV-derived features.
Candidates that WOULD count: tick-level microstructure data, alternative text/news data, satellite or
alternative datasets. Candidates that would NOT count: any further neural architecture applied to
`panel_a_weekly.parquet` or its PANEL-B successor, however novel the architecture.

### PAUSED — No further cross-asset transmission scans without resolving the market-beta question first

Gen-7's Lab 2/Lab 5 (cross-asset transmission — external carriers to Indian equities) found effects
hitting 41/42 sector cells roughly equally, which reads as broad market-beta exposure rather than a
carrier-specific transmission channel. **This is a genuine open sub-question, not a closed one** —
this lab is explicitly NOT dismissing cross-asset transmission as a direction; it is refusing to run
another scan before settling one prior question: *if a future scan again found effects hitting nearly
every sector equally, would detecting "broad market beta responds to carrier X" count as an answer to
the original transmission question, or would it mean the test can't distinguish transmission from
beta and the question needs a different design (e.g., an orthogonalized carrier, or a design that
nets out market beta before testing for sector-specific transmission)?*

**What would reopen it:** a pre-registered answer to that definitional question — likely a Market
Science Lab question, since it is about what a "transmission" claim actually means, not about finding
one. Cross-referenced in `labs/market_science/decision_log/DECISION_LOG.md`. Once resolved, a fresh
cross-asset scan with a design that can tell the two apart is legitimate new work, not a re-run.

### PAUSED — No individual fast-turnover signal from the capital sweep treated as validated alone

G8-07/G8-11's capital-scale sweep of previously-rejected strategies found a real **tier effect**
(non-F&O/low-liquidity names carry more signal, 16/17 signals, p=0.00027) but **no individual
signal** among 1-week reversal, volume surprise, lottery-demand, or 4-week reversal survived
multiple-testing correction on its own. The tier effect is validated; none of the four individual
signals is.

**What would reopen any one of them:** a fresh, single pre-registered test of that one specific
signal (not re-selected from the sweep that found it), with its own power precheck and its own
multiplicity accounting — exactly the discipline `ALPHA-001` already applied to the liquidity
gradient. Re-running the same four-signal sweep and picking whichever looks best this time does not
count.
