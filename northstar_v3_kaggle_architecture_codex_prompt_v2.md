# NORTHSTAR V3 - KAGGLE EXPERIMENTATION ARCHITECTURE REBUILD
## Codex Implementation Prompt
## Priority: Critical
## Date: 2026-04-02

You are working inside the Northstar V3 repository at:

`/path/to/northstar_v3`

This is not a "write a design note and stop" task. This is an implementation task.
Your job is to build a serious Kaggle experimentation architecture inside V3 so repeated research runs are fast, reproducible, versioned, comparable, and hard to mess up.

The architecture must support the immediate weekly research cycle and also become the long-term operating system for Northstar Kaggle experiments.

The user pain is real and specific:

1. Each experiment currently requires too much manual work.
2. Config changes often force code edits.
3. Repo uploads and dataset uploads are not cleanly separated.
4. Notebook-inline execution is causing timeouts.
5. Logs are not structured enough for post-run analysis.
6. Re-running an old experiment weeks later is too error-prone.
7. Comparing experiment 00 through 08 or 09 is too manual.

The end state should feel like this:

1. Researcher chooses or creates `exp_008.yaml`.
2. Researcher changes features, tuning, gates, or notebook selection in config only.
3. Researcher uploads only the smallest changed Kaggle dataset layer.
4. Thin Kaggle notebook imports a runner script and executes one command.
5. Every run writes a complete structured run directory with manifests, logs, metrics, and config snapshots.
6. A comparison CLI can load multiple run outputs and produce side-by-side diagnostics.
7. The architecture is stable enough that repeated Kaggle use becomes routine rather than chaotic.

---

## WHAT MUST GUIDE YOUR DESIGN

This prompt is based on three sources:

1. The main Kaggle architecture brief.
2. The comprehensive research plan for the April 17 freeze review.
3. The weekly sprint plan for the week of 2026-03-29.

Those documents establish the research workload:

1. Multiple notebook stages from NB-00 through NB-07.
2. Repeated walk-forward experiments across many hypotheses.
3. Heavy Kaggle CPU usage, with GPU reserved only where justified.
4. Strong need for reproducibility, regime-aware analysis, and structured evidence.
5. A short freeze-review timeline, so architecture overhead must pay for itself immediately.

The weekly sprint and comprehensive plan are context, not excuses to build an abstract framework disconnected from the repo. Build for the actual codebase.

---

## CURRENT REPO REALITY YOU MUST RESPECT

Before changing anything, understand and design around these repo facts:

1. There is already a Kaggle weekly sprint stack under:
   `scripts/kaggle/week_2026_03_29/`

2. That stack already includes:
   `build_weekly_feature_export.py`
   `nb00_feature_health.py`
   `nb01_fixed_baselines.py`
   `nb02_failed_model_autopsy.py`
   `nb03_regime_dictionary.py`
   `nb04_company_attribution.py`
   `nb05_cross_asset_tests.py`
   `nb06_india_hypothesis_battery.py`
   `nb07_ensemble_tra_deployment.py`
   `run_weekly_suite.py`

3. There is already a Kaggle sprint notebook support layer under:
   `notebooks/kaggle_sprint/shared/`

4. `notebooks/kaggle_sprint/shared/track_a_runner.py` already supports important knobs via env vars such as model filter, feature mode, reduced feature count, raw-financial normalization, and group-ranking enforcement.

5. `scripts/kaggle/week_2026_03_29/common.py` already contains useful shared logic:
   artifact naming
   seed profiles
   regime labels
   sparse event feature stabilization
   JSON helpers

6. There is currently no first-class `configs/` directory driving Kaggle experiments the way we need.

7. There is already a research output area under:
   `data/research/experiments/`

8. The new architecture must harden and extend this existing stack rather than creating a second disconnected Kaggle framework.

This means:

1. Do not throw away the weekly sprint scripts.
2. Do not create parallel duplicate runners unless there is a very strong reason.
3. Prefer refactoring the current weekly scripts to consume shared config/run-management infrastructure.
4. Preserve backward compatibility where practical, especially for existing CLI usage.

---

## PRIMARY OBJECTIVE

Build a config-driven Kaggle experiment operating system for V3 with five big capabilities:

1. Versioned experiment definition.
2. Layered Kaggle dataset/version management.
3. Thin notebook orchestration with heavy logic in Python modules.
4. Structured run logging and artifact persistence.
5. Fast experiment comparison and rerun reproducibility.

This architecture must make it easy to run:

1. `exp_000`
2. `exp_001`
3. `exp_002`
4. ...
5. `exp_008`
6. `exp_009`
7. future runs beyond this sprint

without repeatedly editing Python source just to change feature sets, model settings, promotion gates, regime configs, or notebook selection.

---

## NON-NEGOTIABLE ARCHITECTURE REQUIREMENTS

### R1 - Config-first experiments

Every experiment must be defined by YAML, not by editing Python files.

At minimum, config must control:

1. run id
2. parent run or based-on experiment
3. hypothesis
4. falsification criterion
5. active notebooks/stages
6. feature mode and feature lists
7. dead-filter thresholds
8. preprocessing flags
9. model family enablement
10. model hyperparameters
11. walk-forward settings
12. regime config selection
13. promotion gates
14. logging/output behavior
15. Kaggle dataset references or dataset manifest version ids

Changing the next experiment should usually mean editing one experiment YAML plus maybe one feature-set or model-config YAML.

### R2 - Layered dataset architecture

The architecture must separate slow-changing and fast-changing assets so Kaggle uploads are minimal.

The recommended logical layers are:

1. Raw research bundle dataset
   slow-changing
   contains weekly raw inputs, metadata, event registries, universe master, and source tables

2. Feature export dataset
   medium-changing
   contains `northstar_features.parquet`, splits, regime labels, metadata, and any tiered feature export outputs

3. Code bundle dataset
   fast-changing
   contains `configs/`, `src/`, `scripts/`, notebook support files, and lightweight manifests

4. Run output layer
   generated per Kaggle run
   contains structured logs, metrics, summaries, and comparison-ready artifacts under `/kaggle/working/runs/{run_id}/`

If only config or code changes, the user should not need to re-upload raw data.
If only model tuning changes, the user should ideally only update the code bundle layer.
If only feature filtering changes and the base feature matrix is unchanged, the architecture should avoid forcing a raw-bundle upload.

### R3 - Thin notebook pattern

Notebook code must stay thin.

The desired pattern is:

1. Kaggle notebook cell sets paths and chosen experiment id.
2. Notebook imports a Python runner from the code bundle.
3. Notebook calls one function or one CLI entrypoint.
4. All real logic lives in versioned Python files.

No heavy inline notebook logic.
No long notebook-only pipelines that diverge from repo code.
No hidden state across many cells.

### R4 - Structured logs, not notebook archaeology

Every run must write structured outputs, not just print to notebook cells.

Each run directory must include, at minimum:

1. `run_manifest.json`
2. `merged_config.yaml`
3. `dataset_manifest.json`
4. `environment_manifest.json`
5. `stage_status.json`
6. `summary.json`
7. `window_metrics.parquet` or `.csv`
8. `model_metrics.json`
9. `feature_health_report.json` when NB-00 runs
10. `regime_breakdown.json` when relevant
11. `stdout.log` or equivalent captured log file
12. optional markdown summary for quick human review

If a stage fails, the failure must also be logged in structured form.

### R5 - Deterministic run identity and snapshots

Every run must have:

1. deterministic run id
2. config hash
3. parent experiment reference
4. code bundle version marker
5. dataset version markers
6. created timestamp
7. optional notes/hypothesis snapshot

The exact config used must be snapshotted at run start.
Given a run id, another person should be able to answer:

1. what code bundle was used
2. what datasets were attached
3. what features and models were enabled
4. what hypothesis was being tested
5. what changed versus the prior run

### R6 - Resume and stage-level restart

The architecture must support partial reruns.

Examples:

1. Rerun only NB-01 after changing tree-model tuning.
2. Reuse NB-00 output if feature export did not change.
3. Skip expensive downstream stages until the baseline passes gates.
4. Resume after a Kaggle disconnect using previously written stage artifacts where safe.

This should be controlled by config and/or CLI flags, not by commenting code in and out.

### R7 - Comparison-first experiment management

The user must be able to compare runs quickly.

Provide a comparison tool that can load multiple run directories and report:

1. run metadata
2. config diffs
3. model-level metrics
4. window-level metrics
5. regime breakdown
6. deployment/exposure metrics
7. stage pass/fail status
8. artifact locations

It should be fast enough to use after every Kaggle run.

### R8 - Regime config must be auditable and external

Regime logic must not be trapped in code constants.
Event windows, exposure caps, bucket definitions, and audit thresholds must live in versioned config.

This is especially important because the prior work already exposed regime-boundary and deployment-cap problems.

### R9 - Local/Kaggle parity

A local smoke profile must exist for testing architecture without committing to a full Kaggle run.

The same code path should support:

1. local smoke mode
2. local full mode where possible
3. Kaggle full mode

Differences should be expressed via config/profile, not forked logic.

### R10 - Architecture must serve the weekly plan immediately

The new system must not only look elegant on paper.
It must support the actual weekly research flow:

1. NB-00 through NB-07
2. run-to-run tuning
3. hypothesis tracking
4. freeze-review evidence gathering
5. CPU-heavy Kaggle usage
6. a likely first migration target around the current weekly sprint stack

---

## WHAT SUCCESS LOOKS LIKE

When the architecture is done, the user should be able to do the following with low friction:

1. Create `configs/kaggle/experiments/exp_008.yaml`.
2. Set the experiment to reuse the latest feature export dataset.
3. Change only CatBoost, XGBoost, LightGBM, feature-set, or gate parameters in YAML.
4. Upload only the code bundle dataset if that is the only changed layer.
5. Run a thin Kaggle notebook that points at `exp_008`.
6. Get a run directory with full logs, metrics, manifests, and config snapshots.
7. Compare `exp_007` vs `exp_008` without manual copy-paste.
8. Rerun only a subset of stages if the experiment fails late.

---

## TARGET REPOSITORY SHAPE

Build toward a structure along these lines. Adjust names if needed, but preserve the intent.

```text
northstar_v3/
├── configs/
│   └── kaggle/
│       ├── base.yaml
│       ├── profiles/
│       │   ├── smoke.yaml
│       │   └── full.yaml
│       ├── experiments/
│       │   ├── exp_000.yaml
│       │   ├── exp_001.yaml
│       │   ├── exp_008.yaml
│       │   └── template.yaml
│       ├── features/
│       │   ├── full.yaml
│       │   ├── tier1.yaml
│       │   ├── tier12.yaml
│       │   ├── india_hypothesis.yaml
│       │   └── custom/
│       ├── models/
│       │   ├── tree_rankers.yaml
│       │   ├── tree_regressors.yaml
│       │   └── optional_sequence.yaml
│       ├── regimes/
│       │   ├── base_regimes.yaml
│       │   └── weekly_2026_03_29.yaml
│       └── datasets/
│           └── dataset_manifest.yaml
│
├── src/
│   └── research/
│       └── kaggle/
│           ├── config_loader.py
│           ├── config_diff.py
│           ├── run_context.py
│           ├── run_registry.py
│           ├── artifact_logger.py
│           ├── dataset_manifest.py
│           ├── notebook_runtime.py
│           ├── stage_contracts.py
│           ├── comparison.py
│           └── regime_loader.py
│
├── scripts/
│   └── kaggle/
│       ├── build_code_bundle.py
│       ├── build_dataset_manifest.py
│       ├── compare_runs.py
│       ├── prepare_experiment_bundle.py
│       ├── render_thin_notebook.py
│       └── week_2026_03_29/
│           ├── common.py
│           ├── run_weekly_suite.py
│           ├── nb00_feature_health.py
│           ├── nb01_fixed_baselines.py
│           ├── nb02_failed_model_autopsy.py
│           ├── nb03_regime_dictionary.py
│           ├── nb04_company_attribution.py
│           ├── nb05_cross_asset_tests.py
│           ├── nb06_india_hypothesis_battery.py
│           └── nb07_ensemble_tra_deployment.py
│
├── notebooks/
│   └── kaggle_sprint/
│       ├── templates/
│       ├── weekly/
│       └── shared/
│
└── data/
    └── research/
        └── experiments/
            └── kaggle_runs/
```

Important:

1. Reuse the current weekly scripts where possible.
2. Do not break the existing `scripts/kaggle/week_2026_03_29/` contract unless the migration path is clear.
3. It is acceptable to add a new shared `src/research/kaggle/` layer and gradually migrate the weekly scripts onto it.

---

## REQUIRED DELIVERABLES

### D1 - Config system

Create a first-class Kaggle config system with inheritance/overlay support.

The config system must support:

1. base config
2. profile config
3. experiment override
4. optional CLI/env overrides

Merge order should be explicit and tested.

### D2 - Experiment contract

Define a run contract for each experiment.
At minimum include:

1. `run_id`
2. `experiment_id`
3. `based_on`
4. `hypothesis`
5. `falsification`
6. `owner`
7. `created_at`
8. `code_bundle_version`
9. `dataset_versions`
10. `selected_stages`
11. `expected_outputs`

### D3 - Dataset manifest layer

Introduce a machine-readable dataset manifest that records:

1. logical dataset layer name
2. Kaggle dataset slug if known
3. semantic version or date version
4. expected files
5. optional checksums or row-count guards
6. local path mapping
7. whether the layer is immutable or expected to change often

This should eliminate ambiguity about what a run actually consumed.

### D4 - Shared run context

Implement a shared run-context object or equivalent that all Kaggle stages can use.
It should expose:

1. merged config
2. run id
3. output root
4. dataset manifest
5. environment info
6. stage selection
7. convenience methods for writing artifacts

### D5 - Structured artifact logger

Create a reusable logger/registry layer used across the weekly sprint scripts.
It should support:

1. start stage
2. finish stage
3. fail stage
4. write metrics
5. write tables
6. write config snapshot
7. register artifact paths
8. update summary incrementally

### D6 - Stage refactor of weekly suite

Refactor the current weekly Kaggle suite so each stage can consume the shared config/run infrastructure.

At minimum:

1. `run_weekly_suite.py` should accept an experiment config path or experiment id.
2. Stage scripts should receive run-context-derived paths instead of scattered ad hoc paths.
3. Stage scripts should write into a coherent run directory structure.
4. Existing functionality should continue to work in smoke/full profiles.

### D7 - Thin notebook templates or generators

Provide thin-notebook support so notebook logic is just orchestration.

Acceptable approaches:

1. committed thin notebook templates
2. generated notebooks from a template script
3. a documented minimal notebook contract with generated cells

The important part is that notebooks are dumb launchers and the repo code is the truth.

### D8 - Comparison CLI

Implement a comparison script that can compare multiple runs.
It should support:

1. summary table
2. optional config diff
3. optional artifact presence audit
4. optional stage-status comparison
5. optional export to markdown or csv

### D9 - Documentation

Document:

1. how to create a new experiment
2. how dataset layers work
3. when to update raw bundle vs feature export vs code bundle
4. how to run smoke mode locally
5. how to run on Kaggle
6. how to compare runs
7. how to resume or rerun stages

### D10 - Tests

Add tests for the critical architectural pieces.
Focus on:

1. config merge correctness
2. dataset manifest validation
3. run id and snapshot generation
4. logger output validity
5. comparison tool behavior
6. weekly suite wiring where feasible in smoke mode

---

## HOW TO DESIGN THE DATASET LAYERS

Use a concrete and pragmatic layering model.

### Layer A - Raw research bundle

Purpose:
slow-changing inputs and metadata

Likely contents:

1. raw weekly panel inputs
2. regime event registry
3. universe master
4. macro/cross-asset source tables
5. manual labels and side-data needed by the sprint

### Layer B - Feature export bundle

Purpose:
model-facing export produced from raw bundle plus feature engineering

Likely contents:

1. `northstar_features.parquet`
2. `northstar_walk_forward_splits.json`
3. `northstar_regime_labels.parquet`
4. `northstar_metadata.parquet`
5. `northstar_model_feature_names.json`
6. optional feature-health outputs

### Layer C - Code bundle

Purpose:
fast iteration bundle for Kaggle uploads

Likely contents:

1. `configs/`
2. relevant `src/`
3. relevant `scripts/`
4. notebook utilities
5. tiny manifest files

This bundle should stay as small as possible.

### Layer D - Run outputs

Purpose:
persist per-run evidence and make comparison easy

Likely contents:

1. run manifest
2. merged config
3. metrics
4. tables
5. summaries
6. failures
7. stage-level status
8. optional lightweight markdown memo

Do not design this in a way that requires the user to manually scrape notebook cell output later.

---

## REQUIRED RUN DIRECTORY CONTRACT

Each run directory should look roughly like:

```text
/kaggle/working/runs/{run_id}/
├── run_manifest.json
├── merged_config.yaml
├── dataset_manifest.json
├── environment_manifest.json
├── stage_status.json
├── summary.json
├── stdout.log
├── config_diff_vs_parent.md
├── nb00/
│   ├── feature_health_report.json
│   ├── feature_tiers.csv
│   └── artifact_manifest.json
├── nb01/
│   ├── baseline_results.json
│   ├── window_metrics.parquet
│   ├── model_summary.csv
│   └── artifact_manifest.json
├── nb02/
├── nb03/
├── nb04/
├── nb05/
├── nb06/
└── nb07/
```

Exact filenames may vary, but the contract must be coherent, machine-readable, and comparison-friendly.

---

## HOW THE EXISTING WEEKLY SUITE SHOULD EVOLVE

Use the current weekly suite as the first-class migration target.

### For `scripts/kaggle/week_2026_03_29/run_weekly_suite.py`

Evolve it so it can:

1. load experiment config
2. derive a run context
3. build deterministic stage output directories under a run root
4. allow stage selection or skipping from config/CLI
5. record stage status in a shared manifest
6. preserve smoke/full profile support

### For `scripts/kaggle/week_2026_03_29/common.py`

Preserve useful helpers, but do not let it become a dumping ground.
Move durable architecture logic into `src/research/kaggle/` and keep `common.py` as a thin weekly adapter where appropriate.

### For NB-00 through NB-07 scripts

Refactor only as much as needed to make them consumers of the new architecture.
Do not rewrite scientific logic just for aesthetic purity.
Prioritize:

1. consistent config access
2. consistent artifact writing
3. consistent stage status reporting
4. consistent run-id usage
5. cleaner local/Kaggle parity

---

## EXPERIMENT CONFIG EXAMPLE REQUIREMENTS

Provide at least one real experiment config and one template.

An experiment config should express things like:

```yaml
experiment:
  id: "exp_008"
  run_id: "v3_exp_008_20260402"
  based_on: "exp_007"
  owner: "aryak"
  hypothesis: "Tightening regime windows and externalizing config will improve repeatability and reduce rerun friction while preserving model quality."
  falsification: "If rerunning with the same config cannot reproduce the same stage outputs and comparison metadata, the architecture is not good enough."

profiles:
  active: "full"

datasets:
  raw_bundle: "northstar-v3-weekly-raw:2026-03-29"
  feature_export: "northstar-v3-feature-export:2026-03-29-r2"
  code_bundle: "northstar-v3-kaggle-code:exp_008"

stages:
  run:
    - "nb00"
    - "nb01"
    - "nb03"
    - "nb05"
    - "nb06"
    - "nb07"
  resume_allowed: true

features:
  mode: "tier12"
  custom_set: null
  dead_filter:
    enabled: true
    min_abs_ic: 0.002
    min_abs_tstat: 1.5

preprocessing:
  normalize_raw_financials: true
  sparse_event_ffill: true
  sparse_event_flag_columns: true

models:
  enabled: ["xgboost", "lightgbm", "catboost"]
  catboost:
    depth: 4
    min_data_in_leaf: 40
    l2_leaf_reg: 15.0
    iterations: 800

logging:
  root_dir: "/kaggle/working/runs"
  save_stdout: true
  save_window_metrics: true
  save_regime_breakdown: true
```

The exact schema is up to you, but it must be clean, extensible, and testable.

---

## IMPLEMENTATION PHASES

Work in phases so the result lands cleanly.

### Phase 0 - Audit and map existing Kaggle flow

Before changing code:

1. inspect the current weekly suite
2. inspect current notebook support files
3. identify where config is hardcoded
4. identify where outputs are inconsistent
5. identify what can be wrapped vs what must be refactored

### Phase 1 - Introduce shared config and run-context layer

Build:

1. config loader
2. config schemas or validation helpers
3. dataset manifest support
4. run id generation or normalization
5. snapshot writing

### Phase 2 - Introduce structured run logging

Build:

1. run manifest writer
2. stage status tracker
3. artifact registration
4. summary writer
5. environment manifest writer

### Phase 3 - Integrate weekly suite

Refactor:

1. `run_weekly_suite.py`
2. stage scripts where needed
3. output directory contracts
4. smoke/full profiles through the shared config layer

### Phase 4 - Add comparison and experiment management tooling

Build:

1. run comparison CLI
2. config diff output
3. parent/child experiment awareness
4. optional markdown/csv exports

### Phase 5 - Add notebook-thin support and docs

Provide:

1. thin notebook templates or generator
2. README updates
3. upload/update instructions for Kaggle dataset layers
4. examples for creating a new experiment

### Phase 6 - Verify with smoke tests

Run:

1. unit tests for config/logger/comparison layers
2. smoke-mode weekly suite where feasible
3. artifact inspection to confirm manifests and summaries are created correctly

---

## ACCEPTANCE CRITERIA

The work is done only if the following are true.

### A1 - Config-only rerun workflow works

A new experiment can be created by editing YAML rather than touching multiple Python files.

### A2 - Dataset layering is explicit

There is a clear manifest or documented contract that tells the user exactly which Kaggle dataset layer to update when:

1. raw data changes
2. feature export changes
3. code/config changes
4. only run outputs change

### A3 - Weekly suite runs through shared architecture

The weekly Kaggle suite uses the shared run/config infrastructure rather than bespoke ad hoc path wiring.

### A4 - Structured run artifacts exist

A run produces machine-readable manifests and summaries, not just printed output.

### A5 - Comparison is easy

There is a CLI or script that can compare multiple runs without manual spreadsheet work.

### A6 - Notebook-thin pattern is documented or implemented

The architecture makes notebook timeouts less likely by moving execution into scripts/modules.

### A7 - Smoke verification exists

Critical architecture pieces are verified by tests and at least one practical smoke path.

### A8 - Existing research intent is preserved

The architecture still supports the actual NB-00 to NB-07 research flow described in the weekly and comprehensive plans.

---

## WHAT NOT TO DO

1. Do not build a beautiful but generic framework that ignores the current V3 Kaggle stack.
2. Do not create a second independent experiment system that duplicates `scripts/kaggle/week_2026_03_29/`.
3. Do not force the user to edit Python source between routine experiments.
4. Do not keep major experiment logic trapped in notebook cells.
5. Do not assume full repo re-upload is acceptable for every run.
6. Do not rely on hidden local paths that will not exist on Kaggle.
7. Do not mix run logs, feature exports, and raw bundle artifacts into one ambiguous folder.
8. Do not break the current weekly scripts without a migration path.
9. Do not stop after writing docs. Implement the architecture.

---

## DELIVERABLE FORMAT EXPECTED FROM CODEX

At the end of the implementation, report back with:

1. the architecture decisions you made
2. the files you added or changed
3. how the experiment config flow works
4. how the dataset versioning flow works
5. how to launch a smoke run locally
6. how to launch the Kaggle workflow
7. how to compare two runs
8. what remains intentionally out of scope

Also include any assumptions you made about Kaggle dataset naming or notebook generation.

---

## FINAL INSTRUCTION

Treat this as infrastructure for months of research, not a one-off patch.
The architecture must reduce human error, reduce upload pain, reduce notebook timeout risk, improve reproducibility, and make experiment iteration from `00` through `08` or `09` materially faster.

Build the serious Kaggle experimentation architecture Northstar V3 now needs.
