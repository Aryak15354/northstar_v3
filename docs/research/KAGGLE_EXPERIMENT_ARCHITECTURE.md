# Northstar V3 Kaggle Experiment Architecture

This document describes the config-driven Kaggle experimentation architecture added to V3 for weekly research iteration.

## Goals

- Change routine experiment parameters in YAML, not Python.
- Keep Kaggle uploads small by separating raw data, feature exports, and code.
- Run thin notebooks that import versioned scripts.
- Persist structured run artifacts under `runs/{run_id}/`.
- Compare runs without manual spreadsheet work.
- Preserve provenance back to the actual manual research inputs and canonical reference data.

## Config hierarchy

- `configs/experiment_base.yaml`
- `configs/experiments/run_007.yaml`
- `configs/experiments/run_008.yaml`
- `configs/regime_config.yaml`
- `configs/feature_sets/`
- `configs/model_configs/`

Load a config with:

```bash
python3 -c "from src.research.config_loader import load_experiment_config; import json; print(json.dumps(load_experiment_config('run_008')['experiment'], indent=2))"
```

The merged config now also carries a `_reference_bundle` block pointing at the canonical research reference bundle under `data/canonical/reference/`.

## Reference provenance

The Kaggle experiment stack is now tied back to the real local research inputs, not ad hoc notebook state.

Canonical source tracking lives in:

- `data/canonical/reference/research_inputs_manifest.json`
- `data/canonical/reference/regimes/nse_regime_events_major.parquet`
- `data/canonical/reference/regimes/nse_regime_periods_subtle.parquet`
- `data/canonical/reference/universe/nifty500_universe_enriched.parquet`

Those canonical artifacts are derived from the manual source documents used for V3 research, including:

- `northstar_v3_nse_regime_events_2005_2026.xlsx`
- `Nifty500_Universe_Master.xlsx`
- `nifty500_universe.csv`
- the weekly sprint and comprehensive research plan documents

At runtime:

- the export builder writes `reference_audit` into `weekly_export_manifest.json`
- NB-01 snapshots the reference bundle into `run_manifest.json`, `dataset_manifest.json`, and `summary.json`
- the reference audit validates the export against the canonical Nifty 500 universe before serious runs

## Kaggle dataset layers

Use three Kaggle dataset layers instead of re-uploading the entire repo for every test.

### Layer 1 - Raw export bundle

Purpose:
slow-changing raw inputs and weekly export source data.

Typical contents:

- market data
- regime events
- universe master
- raw weekly research bundle

### Layer 2 - Feature export bundle

Purpose:
model-facing export artifacts.

Typical contents:

- `northstar_features.parquet`
- `northstar_walk_forward_splits.json`
- `northstar_regime_labels.parquet`
- `northstar_metadata.parquet`
- `feature_health_report.json`

### Layer 3 - Code bundle

Purpose:
fast-changing code/config layer.

Typical contents:

- `configs/`
- `src/`
- `scripts/`

Create the code bundle with:

```bash
bash scripts/kaggle/upload_code_dataset.sh
```

## Weekly suite

The weekly Kaggle suite can still run with direct paths, but it now also supports a config-driven run id:

```bash
python3 scripts/kaggle/week_2026_03_29/run_weekly_suite.py --run-id run_008 --profile smoke
```

That creates a registry-backed run directory under `runs/v3_run_008_20260402/` locally or `/kaggle/working/runs/v3_run_008_20260402/` on Kaggle.

The weekly suite now also inventories each stage directory into the run registry so stage outputs are visible from one run root instead of being scattered across ad hoc folders.

## NB-01 runner

The config-driven baseline entrypoint is:

```bash
python3 scripts/kaggle/week_2026_03_29/nb01_runner.py --run-id run_008 --profile smoke
```

This path:

- loads merged YAML config
- resolves the canonical reference bundle and validates it against the export
- snapshots config into the run directory
- applies config-driven feature filtering
- applies the `eps_sue_decay` forward-fill fix
- assigns YAML-driven regime labels and caps to the runtime walk-forward windows
- writes a stage-local filtered export so Track A runs on the corrected experiment-specific splits/regimes
- runs the Track A baseline models
- writes structured logs, deployment metrics, and a run summary

## Run artifacts

Each run writes a structured root:

- `config_snapshot.yaml`
- `merged_config.yaml`
- `run_manifest.json`
- `dataset_manifest.json`
- `environment_manifest.json`
- `stage_status.json`
- `full_log.json`
- `window_events.jsonl`
- `summary.json`

Stage-specific outputs are stored under stage folders such as `nb01/`.

Important runtime guarantees:

- If you pass `--output-dir .../nb01`, the runner still normalizes everything under a single run root and writes stage artifacts to `runs/{run_id}/nb01/`.
- `window_events.jsonl` is append-only and written during model execution so partial progress survives better than a single end-of-run flush.
- `summary.json` now includes deployment exposure metrics, regime config version, and reference bundle provenance for run-to-run auditability.

## Comparing runs

```bash
python3 scripts/kaggle/compare_runs.py v3_run_007_20260331 v3_run_008_20260402
```

The compare tool reads `summary.json` files and prints a compact side-by-side table with model quality, train/test ratio, deployment exposure, and regime config version.
