# Kaggle Run 009 Handoff

This file records the Mac-side preparation already completed for the `run_009` Kaggle experiment.

## Prepared on Mac

- Experiment config: `configs/experiments/run_009.yaml`
- Resolved run id: `v3_run_009_20260403`
- Code bundle zip: `dist/kaggle/northstar_v3_code_bundle_run_009.zip`
- Kaggle code dataset upload folder: `tmp/kaggle_uploads/code_run_009`
- NB-01 Kaggle notebook template: `notebooks/nb01_baselines.ipynb`
- Export-build Kaggle notebook template: `notebooks/nb_export_build.ipynb`

## Verification already completed

- `python3 -m pytest -q tests/research/test_kaggle_experiment_architecture.py tests/research/test_kaggle_weekly_regime_and_feature_fixes.py`
- Result: `13 passed`

## What to upload in Kaggle

For a config-only tuning run, upload only:

- `tmp/kaggle_uploads/code_run_009/`

That folder already contains:

- `dataset-metadata.json`
- `configs/`
- `src/`
- `scripts/`
- `README.md`
- `requirements.txt`

## Kaggle steps for a config-only run

1. Open dataset `northstar-v3-code`
2. Click `New Version`
3. Upload the contents of `tmp/kaggle_uploads/code_run_009/`
4. Open or upload `notebooks/nb01_baselines.ipynb`
5. Attach:
   - `northstar-v3-code`
   - the current export dataset or export notebook output
   - the current NB00 dataset or NB00 notebook output
6. Run all cells
7. Save notebook version

## Kaggle steps if features or raw data changed

1. Upload or open `notebooks/nb_export_build.ipynb`
2. Attach:
   - `northstar-v3-code`
   - `northstar-v3-weekly-raw-inputs`
3. Run and save the export notebook version
4. Run `notebooks/nb00_feature_health.ipynb` against that export output
5. Save the NB00 notebook version
6. Run `notebooks/nb01_baselines.ipynb` against the export + NB00 outputs

## Remaining blocker on Mac

The Kaggle CLI is not authenticated yet because `~/.kaggle/kaggle.json` is missing.
If you add that API token file, the prepared upload folder can be pushed with:

```bash
kaggle datasets version -p /Users/aryakghoshal/Downloads/northstar/northstar_v3/tmp/kaggle_uploads/code_run_009 -m "run_009 code update"
```
