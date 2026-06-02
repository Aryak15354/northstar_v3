# Northstar V3 Weekly Kaggle Sprint

This folder contains the Kaggle-side weekly sprint stack for the `2026-03-29` plan.

Execution order:

1. `build_weekly_feature_export.py`
2. `nb00_feature_health.py`
3. `nb01_fixed_baselines.py`
4. `nb02_failed_model_autopsy.py`
5. `nb03_regime_dictionary.py`
6. `nb04_company_attribution.py`
7. `nb05_cross_asset_tests.py`
8. `nb06_india_hypothesis_battery.py`
9. `nb07_ensemble_tra_deployment.py`
10. `run_weekly_suite.py`

Design choices:

- The weekly raw bundle is treated as the data root.
- A temporary runtime project is created so the research stack can run against Kaggle inputs without silently falling back to hidden local files.
- Screener metrics receive an explicit unit registry so percentages, crores, days, and per-share values are not mixed.
- Model exports and helper metadata are separated:
  - `northstar_features.parquet` is model-facing.
  - `northstar_metadata.parquet` stores sector/market-cap/regime annotations for diagnostics.
- Canonical reference provenance is enforced through `data/canonical/reference/`, which tracks the local regime workbook, the Nifty 500 universe master inputs, and the research plan documents in one manifest.

Config-driven architecture additions:

- `configs/` now holds experiment, feature-set, model, and regime YAMLs.
- `src/research/config_loader.py` materializes a merged config for a run id.
- `src/research/run_registry.py` creates run manifests and stage status files.
- `src/research/experiment_logger.py` writes `full_log.json`, `summary.json`, and append-only `window_events.jsonl`.
- `src/research/reference_data.py` validates the experiment export against the canonical Nifty 500 reference bundle.
- `scripts/kaggle/week_2026_03_29/nb01_runner.py` is the thick config-driven NB-01 runner used by thin notebooks.
- `src/research/regime_assigner.py` now drives runtime walk-forward regime labels from YAML rather than notebook-local hardcoded overlays.

Recommended commands:

```bash
python3 scripts/kaggle/week_2026_03_29/nb01_runner.py --run-id run_008 --profile smoke
```

```bash
python3 scripts/kaggle/week_2026_03_29/run_weekly_suite.py --run-id run_008 --profile smoke
```

NB-01 runtime behavior:

- resolves the run config and canonical reference bundle
- validates the export against the actual Nifty 500 reference universe
- applies experiment-specific feature filtering and preprocessing
- overlays YAML regime assignments and exposure caps onto the runtime splits
- writes a stage-local filtered export under `runs/{run_id}/nb01/`
- persists deployment metrics and comparison output into the registry-backed run root

Run layout:

- `runs/{run_id}/config_snapshot.yaml`
- `runs/{run_id}/run_manifest.json`
- `runs/{run_id}/dataset_manifest.json`
- `runs/{run_id}/stage_status.json`
- `runs/{run_id}/full_log.json`
- `runs/{run_id}/window_events.jsonl`
- `runs/{run_id}/summary.json`
- `runs/{run_id}/nb01/`

Three-dataset Kaggle split:

1. `northstar-v3-export`
   raw or weekly export inputs
2. `northstar-v3-nb00`
   NB-00 feature-health artifacts
3. `northstar-v3-code`
   `configs/`, `src/`, and `scripts/` only
