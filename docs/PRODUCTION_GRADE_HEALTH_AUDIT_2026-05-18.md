# Northstar V3 Production-Grade Health Audit

Date: 2026-05-18  
Scope: local working tree at `/Users/aryakghoshal/Downloads/northstar/northstar_v3`, plus the tracked `origin/main` file set that is now public on GitHub.

## Executive Verdict

Northstar V3 is not production-grade yet. The core issue is not only code quality; it is repository truth. The public GitHub tree, the local working tree, generated runtime artifacts, old backups, reports, snapshots, models, public-readiness edits, deleted tracked files, and untracked replacement code are all mixed together.

The system can show green on the current health command while still containing an active Python syntax error, failing focused tests, production-named mock/synthetic paths, local secret files, hardcoded developer paths, and thousands of files that should not be part of the public source surface.

The quickest honest path to robustness is:

1. Freeze production use until secrets are rotated and the canonical runtime is re-verified.
2. Reconcile local state against GitHub before making more functional changes.
3. Move generated artifacts, old backups, snapshots, models, logs, and temp files out of the public source tree.
4. Add CI gates that catch the failures found in this audit.
5. Split demo/synthetic/mock code from live/production code so there is no accidental fallback into fake behavior.

## Methodology

This audit used local evidence only. No network or remote GitHub API access was required.

Commands and checks used:

- `git status --short --branch`
- `git ls-tree -r --name-only origin/main`
- `git ls-files`
- `git ls-files --others --exclude-standard`
- `du -sh`
- `find . -type f -size +5M`
- `find . -type f -empty`
- `git grep` for `TODO`, `placeholder`, `mock`, `synthetic`, `NotImplementedError`, local paths, Kaggle paths, broad exception handling, random generation, and wall-clock usage
- AST parse check over `src`, `scripts`, `arya`, and `run.py`
- `python3 scripts/ci/check_no_secrets.py`
- `python3 run.py --mode health --verbose`
- `python3 -m pytest --collect-only -q`
- focused pytest runs listed in the validation section

## Quantitative Inventory

| Area | Count / Size | Why it matters |
|---|---:|---|
| Files tracked by GitHub/origin | 3,900 | This is the current public source surface. |
| Local untracked files | 6,676 | Too much unreviewed local-only code/data to reason about production safely. |
| Git status entries | 2,300 | Local tree is heavily divergent from GitHub. |
| Deleted tracked files | 1,271 | Many public files are locally removed but not committed. |
| Modified tracked files | 459 | Large pending change set needs review before public stabilization. |
| Untracked status entries | 570 | New files/directories not represented in GitHub. |
| Tracked backup/archive files | 775 | Public repo still contains historical deadweight. |
| Tracked reports | 677 | Generated reports should not usually live in app source. |
| Tracked snapshots | 519 | Runtime outputs are mixed into source control. |
| Tracked models | 13 | Model artifacts need an explicit artifact policy. |
| Local `data/` | 9.1 GB | Runtime/data artifact bloat. |
| Local `tmp/` | 5.8 GB | Temporary build/smoke/Kaggle outputs are occupying repo root. |
| Local `.git/` | 1.7 GB | History/artifact churn is already heavy. |
| Local `.venv/` + `venv/` | ~959 MB | Two virtualenvs inside the repo; should be ignored/local only. |

## Blocking Findings

### P0: Public Secret Exposure Must Be Treated As Already Compromised

The current tracked-file scanner passes:

```text
python3 scripts/ci/check_no_secrets.py
No obvious secrets found in tracked files.
```

That is good, but it is not enough after a private-to-public flip. Prior tracked `.env.options.bak_*` files were removed locally, and tracked secrets were redacted in the public-readiness pass, but local ignored/private files still contain sensitive material:

- `.env.options`
- `.env.options.bak_20260327_083042`
- `_cold_archive/...`
- `universe/northstar-key.pem`

Production implication: assume anything that was ever pushed before public conversion may be in Git history. Rotate Upstox/Groww/Kalshi/NSE/BSE/email/notification/API credentials, revoke private keys, and remove or rewrite exposed history only after deciding the correct GitHub remediation path.

Required gate:

- Secret scan tracked files on every PR.
- Separate manual history scan with `gitleaks` or equivalent before declaring the public repo safe.
- Keep `.env*`, key material, and broker credentials permanently untracked.

### P0: Local And GitHub States Are Not The Same System

`git status --short --branch` shows 2,300 entries, including 1,271 deleted tracked files, 459 modified tracked files, and hundreds of untracked paths. GitHub has one version of Northstar V3; the local machine has another; production behavior may be a third if local-only data/config is required.

Production implication: no production-grade claim is meaningful until a maintainer can clone the public repo, follow documented setup, run health checks, and get the same canonical behavior without local-only files.

Required gate:

- Create a stabilization branch.
- Commit or intentionally discard each local delta category.
- Produce a `REPO_MANIFEST.md` that declares canonical entrypoints, canonical data layout, and ignored runtime directories.

### P0: Syntax Error Exists Outside The Health Gate

AST parsing found one Python syntax failure:

```text
src/dashboard/enhanced_dashboard.py: invalid syntax (enhanced_dashboard.py, line 286)
```

Local evidence:

```python
with cols[1]:
    vol = contract.get_volatility_regime()
    if vol.is_available:
        ...
    st.metric("Volatility Regime", vol_regime)
else:
    st.metric("Volatility Regime", "UNKNOWN")
```

The `else` is misaligned relative to the `if vol.is_available` block. This file is currently untracked locally, but it is still part of the local codebase and should not be left in a production tree.

Production implication: `python3 run.py --mode health --verbose` can pass while active code is syntactically invalid. That means the health gate is too narrow.

Required gate:

- Add a CI check that parses every active `.py` file under `src`, `scripts`, `tests`, and canonical root entrypoints.
- Exclude only explicitly archived/generated directories.

### P1: Health Checks Are Green While Focused Tests Fail

Current health command:

```text
python3 run.py --mode health --verbose
overall_status: pass
```

But focused checks found real failures:

```text
python3 -m pytest -q tests/intelligence/test_no_synthetic_data.py tests/test_health_exit_codes.py tests/test_dashboard_data_contract.py tests/test_signal_loader_canonical_paths.py
1 failed, 18 passed
```

Failure:

```text
tests/test_signal_loader_canonical_paths.py::test_capital_allocator_normalizes_alpha_os_tailwind_schema
AssertionError: assert '__default__' in {'strategy_recommendations_1': ...}
```

The intelligence observer tests are much more stale:

```text
python3 -m pytest -q tests/intelligence_observer/test_observer_core.py tests/intelligence_observer/test_comprehensive_system.py
27 failed, 14 passed
```

Common failure shape:

- `ObserverSnapshot.__init__()` no longer accepts `timestamp`
- `ObserverContext.current_snapshot` is missing
- `SnapshotBuilder` no longer has `_load_data_sources` / `_assess_data_quality`
- `TemporalIsolation` no longer exposes several tested methods
- weekly report schema no longer includes `report_id`
- one test fixture creates arrays of mismatched length

Production implication: tests are not a coherent contract. Some test modules describe an older API, while the health gate ignores them.

Required gate:

- Split tests into `current_contract`, `legacy_contract`, `integration_slow`, and `research_archive`.
- CI must run the current contract set on every PR.
- Stale tests should be updated or moved out of the blocking suite with an explicit reason.

### P1: Production-Named Mock And Synthetic Paths Still Exist

The codebase contains production-sounding modules that generate or fall back to fake data. Examples from `git grep`:

- `scripts/analysis/generate_3year_backtest.py` creates mock results when missing.
- `scripts/generate_6month_comprehensive_trading_report.py` supplements with synthetic rows.
- `scripts/institutional_12month_simple.py` and related institutional validators generate synthetic data.
- `scripts/integrate_production_grade_with_live_system.py` uses `Mock` risk coordinator / kill switch / trades despite the production name.
- `scripts/northstar_terminal.py` returns a mock snapshot fallback.
- `src/cohesion/sample_data_sources.py` contains mock market/macro/fundamental sources.
- `src/backtesting/backtest_engine.py` has an attribution placeholder.
- `src/operation/stress_testing_system.py`, `src/operation/system_validation_suite.py`, and `src/operation/integration_testing_framework.py` use mock/random validation behavior.
- `src/validation/*` contains many synthetic/mock demos.

Production implication: a live workflow can accidentally look successful while relying on generated or mocked behavior. This is especially dangerous in trading/risk systems.

Required gate:

- Move demo/mock/synthetic code under an explicit namespace such as `examples/`, `research/`, or `archive/`.
- Production modules should fail closed when required real data is unavailable.
- Add a CI guard that rejects `mock`, `synthetic`, `placeholder`, and `sample` usage in `src/production`, live runners, and risk/execution paths, except for allowlisted test files.

### P1: Public Repo Contains Large Deadweight Categories

Tracked GitHub categories that should not be part of a lean public production repo:

- `backups/` and old cleanup archives
- `archive/deprecated/`
- generated reports under `reports/`
- runtime snapshots under `snapshots/`
- model `.pkl` artifacts under `models/`
- old root completion/status docs
- root `run_section_*.py` generated bundle fragments
- root launchers whose relationship to canonical runners is unclear
- old analysis output directories

Production implication: contributors cannot tell what is source, what is output, what is legacy, and what is safe to run. Git history and clone size grow while review quality drops.

Required gate:

- Keep source, tests, docs, and small fixtures in Git.
- Move runtime outputs to ignored storage.
- Move large models to release artifacts, DVC, Hugging Face, S3/GCS, or another declared artifact store.
- Keep only curated sample outputs needed for docs/demo.

### P1: Local Repo Contains Runtime/Data Bloat

Local-only heavy directories and artifacts:

- `data/` at 9.1 GB
- `tmp/` at 5.8 GB
- `.venv/` at 488 MB
- `venv/` at 471 MB
- `logs/` at 40 MB
- `_cold_archive/`
- `dist/kaggle/*.zip`
- `catboost_info/`
- many generated PDF/parquet/sqlite/CatBoost/PyTorch artifacts under `tmp/` and `data/`

Production implication: local runtime state is entangled with source layout. Fresh clones will not reproduce local behavior unless undocumented files exist.

Required gate:

- Keep `data/`, `tmp/`, `logs/`, `dist/kaggle/`, `catboost_info/`, `.venv/`, and `venv/` ignored.
- Add sample fixtures under `tests/fixtures/` or `examples/data/` only when needed.
- Add a data bootstrap command that fails clearly if private datasets are unavailable.

### P1: Hardcoded Local Paths And Fragile Environment Assumptions Remain

Examples:

- `scripts/backup_northstar_data.py` defaults to `/Volumes/NORTHSTAR_BACKUP/northstar_v3`
- `scripts/manage_cron.sh` defaults to `/Volumes/NORTHSTAR_BACKUP/northstar_v3`
- `scripts/run_weekend_maintenance.py` defaults to `/Volumes/NORTHSTAR_BACKUP/northstar_v3`
- several docs/configs still reference `/Users/aryakghoshal/...`
- `/kaggle/input` appears in Kaggle-specific code and should stay isolated to Kaggle runners only

Production implication: scripts encode one developer machine and one storage device. That makes automation brittle and surprises public users.

Required gate:

- All local paths must come from environment variables, config files, or CLI args.
- Config files should use relative paths or documented placeholders.
- CI should reject absolute `/Users/...`, `/Volumes/...`, and machine-specific paths outside docs/examples.

### P2: Root Structure Does Not Tell A New User What Matters

The root contains multiple shell launchers, generated section files, old docs, `.env.options` files, `.DS_Store`, and public-facing source files together. A fresh GitHub visitor cannot quickly identify:

- canonical app entrypoint
- canonical live/paper trading runner
- canonical dashboard
- canonical data update flow
- canonical risk gate
- canonical CI command
- what is legacy or research-only

Production implication: unclear entrypoints cause accidental use of old flows.

Required gate:

- Root should contain only project metadata, top-level docs, and a small number of canonical commands.
- Move launchers into `scripts/runners/` or `ops/`.
- Archive or delete generated `run_section_*.py` files unless they are a documented public artifact.
- Add `docs/ARCHITECTURE.md` and `docs/RUNBOOK.md` links from the README.

### P2: Broad Exception Handling, Wall-Clock Calls, And Randomness Need Contract Boundaries

Pattern scan found:

- `except Exception` in 832 files
- bare `except:` in 76 files
- `pass` in 550 files
- `datetime.now` in 716 files
- `datetime.utcnow` in 35 files
- `np.random` in 187 files
- `random.` in 204 files

These counts include tests and research code, so they are not all defects. The risk is that production modules may silently swallow errors, use uncontrolled wall-clock time, or generate nondeterministic results.

Required gate:

- Risk/execution/live code should use explicit exception types and structured error reporting.
- Time should come from an injectable clock where correctness depends on market date/session.
- Randomness should be seeded or isolated to research/demo paths.

## Deadweight Map

### Remove From Public Git Or Move To External Artifact Storage

These categories are strong deletion/quarantine candidates:

- `backups/`
- `archive/deprecated/`
- `archive/obsolete_cleanup_*`
- `analysis_results/`
- generated `reports/`
- runtime `snapshots/`
- old root completion/status markdown files
- tracked `.env.options.bak_*`
- generated `run_section_*.py` bundle fragments
- tracked binary/model outputs unless intentionally versioned
- old dashboard backups and duplicate dashboard implementations

### Keep, But Clarify Ownership

These are worth keeping only with explicit ownership:

- `src/` as production/library code
- `scripts/ci/` as public quality gates
- `tests/` after splitting current vs legacy contracts
- `docs/` after pruning old completion reports
- `configs/` after removing machine-local absolute paths
- `docs/figures/` only for curated public documentation assets
- `models/` only if model versioning policy is documented

### Local-Only Cleanup Targets

These should remain out of Git and can be cleaned locally after confirming no needed private data is being deleted:

- `data/`
- `tmp/`
- `logs/`
- `.venv/`
- `venv/`
- `_cold_archive/`
- `dist/kaggle/`
- `catboost_info/`
- `.DS_Store`
- `*.pid`
- `nohup.out`

## Production Hardening Plan

### Phase 0: Security Freeze

- Rotate all credentials that may have existed before the public flip.
- Remove local key material from the repo tree.
- Run a history secret scanner.
- Keep public trading credentials impossible by default.

### Phase 1: Reconcile Repo Truth

- Create a stabilization branch.
- Categorize every `git status` entry as `keep`, `delete`, `archive`, or `local-only`.
- Commit public-readiness and cleanup changes in small batches.
- Add a manifest that names canonical source directories and runtime artifact directories.

### Phase 2: CI Gates That Match Reality

Required minimum gates:

- tracked secret scan
- full active Python AST parse
- current-contract pytest smoke suite
- hardcoded local path scan
- no generated artifacts in tracked source
- no mock/synthetic fallback in production paths

### Phase 3: Deadweight Removal

- Delete public tracked backups, snapshots, generated reports, and old archive trees after one manifest-backed review.
- Keep only curated examples and screenshots.
- Move large artifacts to external storage or release assets.

### Phase 4: Runtime Contract Cleanup

- Replace production mock/synthetic fallbacks with explicit failures.
- Move demos and research simulations into clearly named areas.
- Add config validation at startup.
- Make health checks import/parse active modules, not just a narrow list.

### Phase 5: Data And Model Lifecycle

- Define what data is private, generated, sampled, or public.
- Add bootstrap commands for sample/demo mode.
- Define model provenance, checksum, and loading behavior.
- Keep runtime outputs out of source control.

### Phase 6: Observability And Failure Semantics

- Stop swallowing production exceptions.
- Use structured logs for risk/execution/data failures.
- Add exit-code contracts for all runners.
- Add a `--dry-run` and `--strict` mode for public verification.

## Validation Results From This Pass

Passing:

```text
python3 scripts/ci/check_no_secrets.py
No obvious secrets found in tracked files.
```

```text
python3 run.py --mode health --verbose
overall_status: pass
```

```text
python3 -m pytest --collect-only -q
2026 tests collected
```

Previously verified focused tests:

```text
python3 -m pytest -q tests/options/test_dashboard_state_contract.py src/core/tests/test_state_authority.py
11 passed, 1 warning
```

Failing:

```text
python3 -m pytest -q tests/intelligence/test_no_synthetic_data.py tests/test_health_exit_codes.py tests/test_dashboard_data_contract.py tests/test_signal_loader_canonical_paths.py
1 failed, 18 passed
```

```text
python3 -m pytest -q tests/intelligence_observer/test_observer_core.py tests/intelligence_observer/test_comprehensive_system.py
27 failed, 14 passed
```

Structural check failure:

```text
AST parse over src/scripts/arya/run.py:
src/dashboard/enhanced_dashboard.py: invalid syntax at line 286
```

## Production Readiness Score

Current: 4 / 10

Reason: public-facing docs and initial secret hygiene improved, but repository truth, artifact hygiene, CI coverage, stale tests, mock/synthetic boundaries, local-path assumptions, and at least one syntax failure block production-grade confidence.

Near-term target after cleanup and gates: 7 / 10

Required for 8+:

- fresh clone reproducibility
- no local secret files in repo tree
- clean Git status
- small public source surface
- current-contract tests green
- real-data/live paths fail closed
- artifact storage policy enforced

## Immediate Next Actions

1. Rotate/revoke secrets and keys exposed before the public flip.
2. Fix or remove `src/dashboard/enhanced_dashboard.py`.
3. Fix `CapitalAllocator._normalize_tailwind_frame` default handling or update the test contract if the expected behavior changed.
4. Decide whether `tests/intelligence_observer/*` is current contract or legacy contract; update or quarantine accordingly.
5. Commit the public-readiness changes already made, then make a separate deadweight cleanup commit.
6. Delete/move tracked backups, generated reports, snapshots, old archives, and obsolete root docs after review.
7. Add CI gates for AST parse, hardcoded local paths, generated artifacts, and production mock/synthetic usage.
8. Add a fresh-clone smoke script that documents and proves public setup.

## Remediation Applied After This Audit

The first production-hardening pass converted several findings into code and repository changes:

- Fixed the syntax error in `src/dashboard/enhanced_dashboard.py`.
- Fixed Alpha OS tailwind normalization so recommendation-style tailwind rows provide a `__default__` allocator fallback.
- Added CI/local checks for active Python parsing, machine-local path leakage, tracked generated/archive deadweight, and tracked secrets.
- Wired those checks into `run.py --mode health --verbose` and `.github/workflows/v4-stabilization-ci.yml`.
- Removed backup/archive/report/snapshot/tmp/log/runtime artifacts from Git tracking.
- Replaced hardcoded backup paths with `NORTHSTAR_BACKUP_ROOT`, `BACKUP_DEST`, or public placeholder paths.
- Quarantined stale Intelligence Observer tests under `tests/legacy/` and kept the active authority-firewall observer contract green.
- Added `REPO_MANIFEST.md` to declare the public source surface and local-only artifact policy.

## No-Cheats Notes And Limits

This was a broad health audit, not a line-by-line semantic review of all 1,517 Python files. The conclusions are based on quantitative scans, targeted source inspection, syntax parsing, focused test execution, and repository inventory. That is enough to identify the main production blockers, but not enough to certify trading correctness.

Before calling Northstar V3 production-grade, run a clean clone verification from scratch and a Git history secret scan. The local source tree currently contains too much state and too many divergent files for a public user or future maintainer to trust it without this reconciliation.
