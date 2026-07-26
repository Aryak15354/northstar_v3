# Research OS — Shared Infrastructure for the Northstar Research Institute

```
Version:            v1.0
Status:             Frozen
Freeze Date:        2026-07-26
Owner:              Aryak
Depends On:         GEN8_RESEARCH_CHARTER.md §11 (the inheritance contract this module set fulfils),
                    docs/FIELD_REPORT_2026_07_26.md (the evidentiary base for the restructuring)
Used By:            labs/alpha_engine, labs/market_science, labs/microstructure,
                    labs/portfolio_engineering
```

This is the shared statistical and governance infrastructure every one of the four Northstar
Institute labs is required to use. No lab writes its own p-value, power, artifact-check, or ID
logic — that is precisely how Gen-7 ended up with a permutation test floored at zero and two
incompatible object-numbering conventions. Everything here is either forked from Gen-8's own
remediation library (with its 19/19-test track record intact) or new, and is tested the same way
Gen-8's library was: every test builds a case with a known ground truth and shows the naive/old
approach getting it wrong before showing the new module getting it right.

## What's here, and where it came from

| Module | Origin | Fixes |
|---|---|---|
| `valid_pvalue.py` | Forked from `scripts/gen8/lib/valid_pvalue.py` | Permutation p-value floored at 0.0 (Gen-7 CRITICAL-1); resolution-gated multiplicity correction |
| `power_precheck.py` | Forked from `scripts/gen8/lib/power_precheck.py` | Power disclosure as a precondition for a gate (Amendment-002); holdout sizing (Gen-7 CRITICAL-2) |
| `rolling_window_artifact_check.py` | Forked from `scripts/gen8/lib/rolling_window_artifact_check.py` | Overlapping-window construction artifact (Gen-6/MSRP/Gen-8, 5 occurrences project-wide) |
| `registry_integrity_check.py` | Forked from `scripts/gen8/lib/registry_integrity_check.py` | Registry ID schemes and cross-reference integrity (Gen-7 audit HIGH-3/4/5) |
| `experiment_registry.py` | **New** | Manual ID assignment colliding (Gen-5 G5-08B/C) |
| `verdict_schema.py` | **New** | Unlabeled/ambiguous outcomes ("looks promising") never resolving to one of the four established states |
| `preregistration_template.md` | **New** | Pre-registration existing informally per-generation rather than as one enforced template |
| `MASTER_EXPERIMENT_REGISTRY.csv` | **New** | One shared ledger across all four labs — trivial cross-lab referencing (e.g. Microstructure explaining an Alpha Engine finding) |

**Why fork rather than import across directories.** `scripts/gen8/lib/` remains frozen historical
Gen-8 record, per this repository's never-silently-rewrite-history discipline. `GEN8_RESEARCH_CHARTER.md`
§11 itself anticipated this exact moment: *"Gen-9 may inherit: the entire `scripts/gen8/lib/`
remediation library and its tests — it is generation-agnostic infrastructure and is intended to
outlive this generation."* Forking makes `research_os/` the canonical forward-looking copy without
creating a fragile dependency from permanent institute infrastructure onto a single generation's
directory. Confirmed byte-for-byte behaviorally identical to the originals at fork time
(`research_os/tests/test_forked_modules.py`, 19/19, re-running the exact Gen-8 test battery against
the fork).

## The Gen-8 caveat that must travel with every use of the artifact check

`rolling_window_artifact_check.py` is a **conservative one-directional screen, not a clean
discriminator.** First-differencing removes genuine persistence as thoroughly as mechanical
persistence — a random walk, maximally persistent, differences to exactly white noise (verified:
`EXCEEDS_CONSTRUCTION` on both a rolling mean of noise correctly classified `WITHIN_CONSTRUCTION`,
and a random walk correctly classified `EXCEEDS_CONSTRUCTION` despite its differenced series looking
like noise). **Any report using this check must state this caveat inline**, per every lab charter's
binding requirement — do not run it silently as if a passing result were dispositive on its own.

## How a lab registers and closes an experiment

```python
from research_os.experiment_registry import register_experiment, close_experiment

eid = register_experiment(
    lab="microstructure",
    hypothesis_one_line="Delisting exit fills degrade linearly with days-to-delisting, not abruptly",
    preregistration_path="labs/microstructure/protocols/MICRO-001_EXIT_FILL_MODEL.md",
)
# ... run the pre-registered analysis, using power_precheck / rolling_window_artifact_check as needed ...
close_experiment(eid, verdict="VALIDATED", closing_doc_path="labs/microstructure/results/MICRO-001/FINDINGS.md")
```

`close_experiment` refuses to accept anything outside the four-value verdict schema
(`VALIDATED / REJECTED / INCONCLUSIVE / METHODOLOGICAL_FAILURE`), and `verdict_schema.assert_closeable`
additionally refuses `VALIDATED`/`REJECTED` without a stated power figure and refuses any claim
involving a windowed feature without a stated artifact-check result. These are hard gates, not
checklist reminders — the whole point, per the Gen-7 postmortem, is that a discipline stated only in
a document gets skipped under time pressure; a discipline enforced in code does not.

## Registry schema

`MASTER_EXPERIMENT_REGISTRY.csv`: `experiment_id, lab, date_registered, hypothesis_one_line,
preregistration_path, status, verdict, closing_doc_path`. Append-only in the sense that matters: no
row's `experiment_id` is ever dropped or reassigned once created (`test_close_never_drops_a_row`);
`status` and `verdict` transition in place on the same row as the experiment moves from `REGISTERED`
to `CLOSED`, mirroring the same state-machine pattern `GEN7_RESEARCH_CHARTER.md`'s own object
registries already use (Candidate → Validated → Promoted → Frozen on one row, never a new row per
state).

## Tests

```bash
venv_gen8/bin/python3 -m research_os.tests.test_research_os       # 13/13 — new modules
venv_gen8/bin/python3 -m research_os.tests.test_forked_modules     # 19/19 — forked modules, re-verified
```

## What this does not do

- Does not itself enforce that a pre-registration document exists before `register_experiment` is
  called — that discipline is enforced by review and by each lab's charter, not by this code, because
  a pre-registration is sometimes drafted in the same commit as its own registration.
- Does not adjudicate economic validity — that is Alpha Engine's and Portfolio Engineering's charter-
  specific standard (the Universal Oracle Ladder), deliberately kept out of shared infrastructure so
  Market Science and Microstructure's charters, which forbid Sharpe-based validation entirely, cannot
  accidentally inherit it.

## Known limitation, flagged 2026-07-26 (ALPHA-002)

`power_precheck`'s formula treats `n` as a count of raw i.i.d. correlation pairs. Several experiments
(`ALPHA-001`, `ALPHA-002`, `MSCI-001..003`) instead test the mean of a time series of already-
aggregated weekly cross-sectional statistics (an IC or a regression coefficient, each itself estimated
from ~100-500 stocks) via a Newey-West mean test — a different, generally better-powered design that
this formula's correlation-power heuristic understates. `ALPHA-002` observed this directly: a
univariate effect the formula rated at 8.5% power came back at `p<0.0001`. The heuristic is kept as
the default (it is conservative, and disclosing an artificially strict gate is safer than an overly
generous one), but a future session should add an NW-mean-test-specific power calculator — modeled on
`G8-09`'s own `se_sharpe`-based paired-difference approach — as a selectable alternative `test_design`
in this module, so aggregated-statistic experiments are not forced to either misreport their `n` or
carry a known-conservative caveat in every findings doc.
