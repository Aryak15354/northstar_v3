# Repo Stabilization Blueprint

Date: 2026-03-20  
Scope: make `northstar_v3` small enough to reason about, strict enough to trust, and explicit enough to finish

## Goal

The repo does not need to become small in an absolute sense. It needs to become bounded.

The real problem is not just size. The problem is that too many files, directories, wrappers, archives, generated artifacts, and stale completion docs are all competing to look "active."

This blueprint defines how to get from that state to one where we can eventually make a defensible claim that nothing material is left unresolved inside the active system surface.

## What "Nothing Is Left" Actually Means

We should not use that phrase casually. In this repo, it should only mean:

1. The active system surface is explicitly defined.
2. Everything outside that surface is quarantined, archived, or treated as generated artifacts.
3. The active surface has no missing imports, no placeholder runtime paths, and no schema ambiguity on core datasets.
4. Test discovery is bounded to the active test surface.
5. Health, pre-open, and runtime checks agree on severity and intent.
6. Documentation describes the active system that actually exists, not historical plans or optimistic completion claims.
7. Unknown areas are either audited or removed from the canonical surface.

If those conditions are not met, then the honest phrase is not "nothing is left." The honest phrase is "the system is still not fully stabilized."

## Current Manageability Problem

Top-level reality today:

- `src`: 31M
- `scripts`: 15M
- `tests`: 15M
- `docs`: 5.0M
- `_cold_archive`: 19M
- `reports`: 17M
- `snapshots`: 7.1M
- `analysis_results`: 9.9M
- `data`: 6.5G

Root-level clutter today includes:

- active code and entrypoints
- generated data and reports
- local environments
- archived trees
- duplicated standalone subsystems
- test artifact roots
- legacy dashboard roots

This is why the repo feels unfinishable. The active boundary is not enforced.

## Canonical Surface: What We Should Keep Active

This is the working set that should remain in the primary operator/developer surface.

### Primary code and config

- `src/`
- `scripts/`
- `tests/`
- `config/`
- `docs/operations/`
- `docs/stabilization/`

### Primary root files

- `README.md`
- `ROOT_FOLDER_README.md`
- `Makefile`
- `requirements.txt`
- `run.py`
- `run_daily_v3.py`
- `run_complete_v3_system.py` as a wrapper only if intentionally retained

### Primary runtime artifacts

These stay in the repo working directory, but they are not part of the code-review surface:

- `data/`
- `logs/`
- `models/`
- `universe/`

### Primary external integration surface

- `ns_uso/`

Reason:

- it is still referenced by automation and sentiment bridge code
- it is part of the active sentiment/export path

## Secondary But Legitimate Surfaces

These are allowed to exist, but they should not compete with the canonical working set.

- `deployment/`
- `examples/`
- `data_dictionary/`

Required rule:

- they must be documented as secondary
- they must not be treated as authoritative runtime entrypoints

## Root-by-Root Decision Table

| Root | Decision | Why |
| --- | --- | --- |
| `src/` | keep active | primary product code |
| `scripts/` | keep active, then reduce | operational surface is still needed |
| `tests/` | keep active, then normalize fixtures | primary regression surface |
| `config/` | keep active | runtime and research configuration |
| `docs/operations/` | keep active | operator guidance |
| `docs/stabilization/` | keep active | stabilization plans and hardening rules |
| `data/` | keep generated-active | runtime artifacts required by the system |
| `logs/` | keep generated-active | runtime evidence, not source |
| `models/` | keep generated-active | active model artifacts |
| `universe/` | keep generated/reference-active | active reference datasets and universe files |
| `ns_uso/` | keep active | current sentiment/export dependency surface |
| `_cold_archive/` | quarantine immediately | historical material should not influence active discovery |
| `archive/` | quarantine immediately | deprecated material |
| `analysis_results/` | quarantine immediately | generated analysis output, not active code |
| `reports/` | quarantine immediately from active engineering surface | generated output, too much noise |
| `snapshots/` | quarantine immediately from active engineering surface | generated state/history |
| `fund_grade_reports/` | move under generated/reporting area | artifact output, not source |
| `.hypothesis/` | remove from tracked surface | generated test cache |
| `__pycache__/` | remove from tracked/visible surface | local bytecode cache |
| `.venv/`, `venv/` | keep local-only, never part of repo reasoning surface | environment noise |
| `tmp/` | quarantine/remove | temporary workspace noise |
| `dashboard/` | quarantine as deprecated root | `config/system_surface.yaml` already marks `dashboard/volatility_dashboard.py` as legacy |
| `northstar/` | investigate, likely merge-or-archive | appears to be an older parallel NS-USO surface |
| `system/` | investigate, likely split/move | mixed state artifacts plus status script |
| `ingestion/` | remove if still only scaffolding | top-level folder is empty placeholder structure |
| `test_config/` | migrate into `tests/fixtures/` then remove from root | test artifact root |
| `test_simple_config/` | migrate into `tests/fixtures/` then remove from root | test artifact root |
| `test_schemas/` | migrate into `tests/fixtures/` then remove from root | test artifact root |
| `test_simple_schemas/` | migrate into `tests/fixtures/` then remove from root | test artifact root |
| `test_integration_schemas/` | migrate into `tests/fixtures/` then remove from root | test artifact root |
| `integration_test_schemas/` | migrate into `tests/fixtures/` then remove from root | test artifact root |
| `data_dictionary/` | move under docs or explicitly mark as reference-only | docs, not runtime |
| `examples/` | keep secondary or archive | should not compete with runtime |
| `deployment/` | keep secondary | useful, but not the daily working set |

## Ambiguous Roots That Need Explicit Decisions

### `northstar/`

Observed state:

- contains `northstar/scripts/run_v3_batch_ingestion.py`
- contains `northstar/northstar_terminal.py`
- overlaps in purpose with `ns_uso/`

Observed risk:

- active docs and tests still reference it in places
- it creates a second sentiment/ingestion story at the repo root

Decision required:

- either merge all still-needed behavior into `ns_uso/`
- or archive `northstar/` and update the remaining references

Default recommendation:

- treat `ns_uso/` as canonical
- treat `northstar/` as merge-and-retire candidate

### `dashboard/`

Observed state:

- only contains `dashboard/volatility_dashboard.py`
- `config/system_surface.yaml` already labels that file as a deprecated pattern
- multiple docs still mention `streamlit run dashboard/volatility_dashboard.py`

Decision required:

- remove it from the active operator path
- archive it or keep it only as explicitly deprecated legacy UI

Default recommendation:

- quarantine it
- update docs to point only at `src/dashboard/app.py`

### `system/`

Observed state:

- contains `system/check_system_status.py`
- also contains state-like files such as `THE_CRITICAL_ANSWER.json`, `sealed_results.json`, and `system_freeze_hash.txt`

Observed risk:

- mixed source and artifact semantics in one root

Default recommendation:

- move the script into `scripts/`
- move state files into a generated/state directory if still needed
- remove `system/` as a top-level code root

### Test artifact roots

Observed state:

- cleanup tooling already identifies these roots as artifacts:
  - `test_config`
  - `test_simple_config`
  - `test_schemas`
  - `test_simple_schemas`
  - `test_integration_schemas`
  - `integration_test_schemas`
- active tests still reference some of them by path

Default recommendation:

- do not delete them blindly
- move them under `tests/fixtures/`
- rewrite tests to use fixture-relative paths
- then remove the root-level versions

## Existing Repo Signals We Should Reuse

The repo already contains useful manageability signals:

- `config/system_surface.yaml`
- `scripts/cleanup/move_planner.py`
- `scripts/cleanup/file_analyzer.py`

That means we do not need to invent the concept of a canonical surface from scratch. We need to harden and enforce it.

### Why `config/system_surface.yaml` matters

It already identifies:

- canonical entrypoints
- operational surfaces
- deprecated patterns

But it is not yet strict enough because:

- it still lists legacy-like surfaces such as `launch_old_dashboard.sh`
- it does not yet define quarantine roots
- it is not being enforced strongly enough across docs, scripts, and tests

## Immediate Enforcement Changes

These are the smallest changes that pay back the most manageability.

### 1. Bound test discovery at the repo root

Done in this pass:

- added `pytest.ini`
- discovery is now scoped to `tests/`
- archive and generated roots are excluded from recursion

Expected effect:

- `_cold_archive/` and similar roots stop polluting test collection
- pytest root becomes this repo, not the parent directory

### 2. Freeze the canonical surface in one place

Next required change:

- update `config/system_surface.yaml` so it explicitly declares:
  - primary roots
  - secondary roots
  - quarantine roots
  - deprecated roots

### 3. Move test artifacts under `tests/fixtures/`

Reason:

- root-level test data roots create noise and make the repo look larger and stranger than it really is

### 4. Stop treating generated outputs as source surfaces

Applies to:

- `reports/`
- `snapshots/`
- `analysis_results/`
- `fund_grade_reports/`

Needed behavior:

- these roots can remain on disk
- they should not be used as default search or review surfaces
- they should be documented as generated outputs

### 5. Collapse duplicate subsystem stories

Priority examples:

- `ns_uso/` vs `northstar/`
- `dashboard/` root vs `src/dashboard/`
- root wrappers vs script implementations
- `config/operation_config.yaml` vs `config/operation/operation_config.yaml`

## First Cleanup Sequence

This is the sequence that makes the repo materially more manageable without immediately risking business logic changes.

### Wave 1: Surface reduction without semantic risk

1. Keep using the new `pytest.ini`.
2. Move root-level test artifact directories into `tests/fixtures/`.
3. Mark `_cold_archive/`, `archive/`, `analysis_results/`, `reports/`, and `snapshots/` as quarantine roots in the canonical surface spec.
4. Move `data_dictionary/` under `docs/`.
5. Move or quarantine `dashboard/volatility_dashboard.py`.

### Wave 2: Resolve ambiguous duplicate roots

1. Decide between `ns_uso/` and `northstar/`.
2. Split or remove the `system/` root.
3. Delete the top-level `ingestion/` scaffolding folder if it remains placeholder-only.

### Wave 3: Stabilize active runtime truth

1. fix missing imports in active canonical packages
2. remove placeholder logic from canonical runtime paths
3. align docs with the surviving runtime surface

## Definition Of Done For Repo Manageability

We can call the repo manageable when all of the following are true:

### Surface

- one canonical dashboard surface
- one canonical runtime surface
- one canonical operation config surface
- one canonical sentiment company schema
- one canonical sentiment market schema

### Discovery

- pytest only discovers active tests
- no archive roots affect active validation
- generated roots are excluded by default from engineering search/review

### Structure

- no root-level test artifact directories remain
- no deprecated dashboard root remains active
- no ambiguous duplicate subsystem root remains without an explicit reason

### Runtime trust

- canonical imports resolve cleanly
- no placeholder/mock/stub logic remains on canonical runtime paths
- health/pre-open/runtime status surfaces agree on what is a blocker

### Documentation trust

- “complete”, “deployment ready”, and “real data only” claims match actual code
- stale completion reports no longer function as operational truth

## What I Recommend We Do Next

If the goal is to make the repo manageable, the next concrete sequence should be:

1. keep `pytest.ini` and verify the reduced collection surface
2. migrate the root test artifact directories into `tests/fixtures/`
3. update `config/system_surface.yaml` into a strict source-of-truth file
4. quarantine `dashboard/`, `_cold_archive/`, `archive/`, `analysis_results/`, `reports/`, and `snapshots/` from the active engineering surface
5. decide `ns_uso/` versus `northstar/`

That is the shortest path from “huge and unknowable” to “bounded and auditable.”

## Final Principle

We do not get to "nothing is left" by reading every file forever.

We get there by making the repo small enough in practice that the only files still allowed to matter are the ones we intentionally kept alive.
