# Northstar V3 Kaggle Experiment Runbook

This runbook is the operator-facing command guide for the config-driven Kaggle experiment architecture.

## 1. Local shell setup

From the repo root:

```bash
cd /Users/aryakghoshal/Downloads/northstar/northstar_v3
```

If you want a fresh virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
python3 -m pip install catboost lightgbm xgboost
export PYTHONPATH="$PWD"
```

If the existing `venv/` is already good:

```bash
cd /Users/aryakghoshal/Downloads/northstar/northstar_v3
source venv/bin/activate
export PYTHONPATH="$PWD"
```

## 2. Sanity checks before any run

Confirm the canonical reference bundle exists and the architecture tests pass:

```bash
python3 -m pytest -q tests/research/test_kaggle_experiment_architecture.py tests/research/test_kaggle_weekly_regime_and_feature_fixes.py
```

Optional wider test pass:

```bash
python3 -m pytest -q
```

## 3. Create the next experiment config

Copy the previous experiment YAML and edit only the fields you want to tune.

Example for `run_009`:

```bash
cp configs/experiments/run_008.yaml configs/experiments/run_009.yaml
```

Then edit:

```bash
nano configs/experiments/run_009.yaml
```

Update at minimum:

- `experiment.run_id`
- `experiment.description`
- `experiment.based_on`
- `experiment.hypothesis`
- any override blocks for the next tuning step

If the regime boundaries or exposure caps change, edit:

```bash
nano configs/regime_config.yaml
```

## 4. Fast local smoke run for NB-01

This is the safest preflight check before a real Kaggle run:

```bash
python3 scripts/kaggle/week_2026_03_29/nb01_runner.py \
  --run-id run_008 \
  --profile smoke \
  --max-splits 1 \
  --output-dir tmp/preflight_nb01/nb01
```

That writes everything under:

```bash
tmp/preflight_nb01/v3_run_008_20260402/
```

Key files to inspect after the smoke run:

```bash
cat tmp/preflight_nb01/v3_run_008_20260402/summary.json
cat tmp/preflight_nb01/v3_run_008_20260402/stage_status.json
head -20 tmp/preflight_nb01/v3_run_008_20260402/window_events.jsonl
```

## 5. Full local NB-01 run

Use this when you want a serious local run against the full export path:

```bash
python3 scripts/kaggle/week_2026_03_29/nb01_runner.py \
  --run-id run_008 \
  --profile full \
  --output-dir runs_local/nb01
```

If you want to point at a specific export and NB-00 report:

```bash
python3 scripts/kaggle/week_2026_03_29/nb01_runner.py \
  --run-id run_008 \
  --export-dir /absolute/path/to/00_export \
  --nb00-report /absolute/path/to/feature_health_report.json \
  --profile full \
  --output-dir runs_local/nb01
```

## 6. Full weekly-suite smoke run

Use this to verify the whole weekly sprint wiring:

```bash
python3 scripts/kaggle/week_2026_03_29/run_weekly_suite.py \
  --run-id run_008 \
  --profile smoke \
  --max-splits 1 \
  --continue-on-error \
  --output-root tmp/weekly_suite_smoke
```

## 7. Full weekly-suite run

```bash
python3 scripts/kaggle/week_2026_03_29/run_weekly_suite.py \
  --run-id run_008 \
  --profile full \
  --continue-on-error \
  --output-root runs_weekly
```

If you have a separately versioned raw weekly bundle, point the suite at it:

```bash
python3 scripts/kaggle/week_2026_03_29/run_weekly_suite.py \
  --run-id run_008 \
  --data-dir /absolute/path/to/weekly_raw_bundle \
  --profile full \
  --continue-on-error \
  --output-root runs_weekly
```

## 8. Build the code dataset bundle for Kaggle

Whenever only `configs/`, `src/`, or `scripts/` changed:

```bash
bash scripts/kaggle/upload_code_dataset.sh
```

Or specify the output filename explicitly:

```bash
bash scripts/kaggle/upload_code_dataset.sh northstar_v3_code_bundle_run_008.zip
```

The zip lands in:

```bash
dist/kaggle/
```

## 9. Rebuild the feature export layer

Use this when the underlying feature engineering changed, not when only model config changed:

```bash
python3 scripts/kaggle/week_2026_03_29/build_weekly_feature_export.py \
  --profile full \
  --output-dir tmp/feature_export_full/00_export
```

Smoke example:

```bash
python3 scripts/kaggle/week_2026_03_29/build_weekly_feature_export.py \
  --profile smoke \
  --output-dir tmp/feature_export_smoke/00_export
```

If using a dedicated weekly raw bundle:

```bash
python3 scripts/kaggle/week_2026_03_29/build_weekly_feature_export.py \
  --data-dir /absolute/path/to/weekly_raw_bundle \
  --profile full \
  --output-dir tmp/feature_export_full/00_export
```

## 10. Compare completed runs

Preferred command:

```bash
python3 -m src.research.compare_runs v3_run_007_20260331 v3_run_008_20260402 --runs-root runs
```

Thin wrapper form:

```bash
PYTHONPATH=. python3 scripts/kaggle/compare_runs.py v3_run_007_20260331 v3_run_008_20260402 --runs-root runs
```

## 11. Kaggle notebook flow

Attach these dataset layers:

1. raw/export dataset
2. NB-00 artifact dataset if needed
3. code bundle dataset

Notebook cell 1:

```python
import subprocess
import sys

subprocess.run(
    [sys.executable, "-m", "pip", "install", "catboost", "lightgbm", "xgboost", "pyyaml", "--quiet", "--break-system-packages"],
    check=True,
)
```

Notebook cell 2:

```python
import sys
sys.path.insert(0, "/kaggle/input/northstar-v3-code/northstar_v3_latest")
```

Notebook cell 3:

```python
from scripts.kaggle.week_2026_03_29.nb01_runner import run_experiment

results = run_experiment("run_008")
results
```

## 12. What to run for each type of change

If you changed only model tuning or feature-selection config:

1. edit `configs/experiments/run_00X.yaml`
2. run architecture tests
3. run local smoke NB-01
4. rebuild only the code dataset zip
5. run Kaggle notebook

If you changed regime boundaries:

1. edit `configs/regime_config.yaml`
2. run architecture tests
3. run local smoke NB-01
4. rebuild only the code dataset zip
5. rerun Kaggle

If you changed feature engineering or raw export generation:

1. rebuild the weekly feature export
2. rerun NB-00 if needed
3. run local smoke NB-01
4. update the Kaggle feature export dataset
5. rerun Kaggle

## 13. Most important output files after a run

For a completed run, inspect:

```bash
cat runs/v3_run_008_20260402/config_snapshot.yaml
cat runs/v3_run_008_20260402/summary.json
cat runs/v3_run_008_20260402/stage_status.json
head -20 runs/v3_run_008_20260402/window_events.jsonl
```

For the stage-local runtime export:

```bash
cat runs/v3_run_008_20260402/nb01/tier12_export/weekly_export_manifest.json
```

That manifest is where you confirm:

- reference audit
- experiment run id
- regime config version
- runtime regime assignment
