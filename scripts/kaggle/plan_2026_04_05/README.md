# Northstar V3 Compendium Experiment Suite

This folder contains the v1 experiment stack aligned to the `2026-04-05` compendium plan.

Design rules:

- One master notebook drives the suite: [master_experiment_suite_v1.ipynb](/Users/aryakghoshal/Downloads/northstar/northstar_v3/notebooks/kaggle_sprint/master_experiment_suite_v1.ipynb)
- The experiment contract is catalog-driven from [catalog_v1.yaml](/Users/aryakghoshal/Downloads/northstar/northstar_v3/configs/plan_2026_04_05/catalog_v1.yaml)
- `EXP-09` through `EXP-27` are explicit and versionable
- All verification runs assume the verified Kaggle-ready export, not a raw rebuild

Files:

- [run_plan_suite.py](/Users/aryakghoshal/Downloads/northstar/northstar_v3/scripts/kaggle/plan_2026_04_05/run_plan_suite.py): CLI entrypoint for running one or more experiments
- [nb_exp_master.py](/Users/aryakghoshal/Downloads/northstar/northstar_v3/scripts/kaggle/plan_2026_04_05/nb_exp_master.py): notebook-friendly wrapper
- [ratio_campaign.py](/Users/aryakghoshal/Downloads/northstar/northstar_v3/scripts/kaggle/plan_2026_04_05/ratio_campaign.py): `EXP-09` to `EXP-12`
- [sector_campaign.py](/Users/aryakghoshal/Downloads/northstar/northstar_v3/scripts/kaggle/plan_2026_04_05/sector_campaign.py): `EXP-13` to `EXP-16`
- [regime_campaign.py](/Users/aryakghoshal/Downloads/northstar/northstar_v3/scripts/kaggle/plan_2026_04_05/regime_campaign.py): `EXP-17` to `EXP-19`
- [model_redemption.py](/Users/aryakghoshal/Downloads/northstar/northstar_v3/scripts/kaggle/plan_2026_04_05/model_redemption.py): `EXP-20` to `EXP-23`
- [signal_expansion.py](/Users/aryakghoshal/Downloads/northstar/northstar_v3/scripts/kaggle/plan_2026_04_05/signal_expansion.py): `EXP-24` and `EXP-25`
- [signal_verification.py](/Users/aryakghoshal/Downloads/northstar/northstar_v3/scripts/kaggle/plan_2026_04_05/signal_verification.py): `EXP-26` and `EXP-27`

Recommended commands:

```bash
python3 /Users/aryakghoshal/Downloads/northstar/northstar_v3/scripts/kaggle/plan_2026_04_05/run_plan_suite.py --list
```

```bash
python3 /Users/aryakghoshal/Downloads/northstar/northstar_v3/scripts/kaggle/plan_2026_04_05/run_plan_suite.py \
  --export-dir /Users/aryakghoshal/Downloads/northstar/northstar_v3/tmp/northstar_v3_chunk_build_2019_merge_verify \
  --output-root /Users/aryakghoshal/Downloads/northstar/northstar_v3/runs/compendium_plan_v1 \
  --exp-id EXP-09 \
  --profile full
```

```bash
python3 /Users/aryakghoshal/Downloads/northstar/northstar_v3/scripts/kaggle/plan_2026_04_05/run_plan_suite.py \
  --export-dir /Users/aryakghoshal/Downloads/northstar/northstar_v3/tmp/northstar_v3_chunk_build_2019_merge_verify \
  --output-root /Users/aryakghoshal/Downloads/northstar/northstar_v3/runs/compendium_plan_v1 \
  --exp-id EXP-24 \
  --exp-id EXP-25 \
  --exp-id EXP-26 \
  --exp-id EXP-27 \
  --profile full
```

Output layout:

- `runs/compendium_plan_v1/exp_09_v1/summary.json`
- `runs/compendium_plan_v1/exp_09_v1/economic_narrative.md`
- `runs/compendium_plan_v1/exp_09_v1/artifacts/...`
- `runs/compendium_plan_v1/suite_summary.json`

Versioning rule:

- Keep the notebook and runner stable
- Clone the catalog to `catalog_v2.yaml`, `catalog_v3.yaml`, and so on as tuning decisions become locked in
- Store each rerun under a new `output-root` or a new `version` flag to preserve historical evidence
