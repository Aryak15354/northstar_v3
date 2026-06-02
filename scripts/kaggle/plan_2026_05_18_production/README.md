# Northstar V3 Fixed-Export Kaggle Experiments

This package runs the Run 4 cleaned experiment suite against the repaired feature
export and the validated sequence export.

```bash
python run_experiment.py EXP-09
python run_experiment.py EXP-10
python run_experiment.py EXP-11
python run_experiment.py EXP-12
python run_experiment.py EXP-13
python run_experiment.py EXP-14
python run_experiment.py EXP-15
python run_experiment.py EXP-16
python run_experiment.py EXP-17
python run_experiment.py EXP-18
python run_experiment.py EXP-19
python run_experiment.py EXP-20
python run_experiment.py EXP-21
python run_experiment.py EXP-22
python run_experiment.py EXP-23
python run_experiment.py EXP-24
```

For the complete Run 4 suite, including modular tabular EXP-09..19, true
sequence EXP-20..23, and diagnostics through EXP-24, use:

```bash
bash ../run_all_northstar_experiments.sh
```

On Kaggle, attach the private dataset `aryakghoshal/northstar-v3-feature-export-fixed`.
The runner automatically resolves `/kaggle/input/northstar-v3-feature-export-fixed`.
If Kaggle mounts datasets under the nested path, pass the data directory explicitly:

```bash
python run_experiment.py EXP-09 \
  --data-dir /kaggle/input/datasets/aryakghoshal/northstar-v3-feature-export-fixed
```

The runner includes production guards for CatBoost walk-forward runs:

- Avoids noisy RMSE early stopping by using fixed low-LR iterations for Run 4 tabular models.
- Records prediction dispersion, fit mode, raw ratio, capped robust ratio, and degenerate windows.
- Uses robust median train/test ratio for gates and candidate selection, so near-zero IC windows cannot explode the aggregate.

Next-batch policy from the PDF log review:

- Default policy is `full` features for EXP-09..19 and EXP-24 so sparse macro/event columns stay available to CatBoost.
- Training windows are post-Ind-AS rolling windows anchored at `2021-04-01`; the 2019 expanding anchor is no longer used.
- Validation splits are retained for diagnostics and non-default modes; the default Run 4 tabular model does not early-stop on RMSE validation loss.
- Structural-event exclusion is date-range based, not hard-coded by window index.
- EXP-09 now tests depth 6 Plain+Depthwise with `min_data_in_leaf` values 80/150/250.
- A preflight check verifies fresh Run 4B code markers, the sequence dataset, and CUDA before expensive training starts.
- Primary CatBoost training now uses fixed low-LR iterations instead of RMSE early stopping, so fallback is no longer the real model.
- Leaf-size experiments use Plain + Depthwise CatBoost because `min_data_in_leaf` is not an effective control under default symmetric trees.
- Zero-feature IC-screen windows are skipped cleanly instead of crashing CatBoost.
- EXP-11 is closed as an explicit no-rerun result because Run 3 answered Ordered vs Plain.
- EXP-10 removes the harmful L2 sweep and tests row subsampling instead.
- EXP-13 uses sector-local 70% null filtering and top-10 force-kept FS features.
- EXP-14 removes FX force-keeps and excludes extreme negative-IC windows from aggregates.
- EXP-15 is gated to bull regimes only.
- EXP-16 logs R3/R9 regime counts, gates out R6 Sideways, and uses a dedicated R4 setup.
- EXP-19 uses a 1,500-row regime floor and zero-feature skip behavior.
- EXP-20..23 are reopened in `../sequence_experiments/run_sequence_experiment.py`
  and use the validated sequence tensor export.
- The run-all script writes rolling and final results archives to `/kaggle/working`.
- EXP-25..27 are excluded from the default Run 4 suite and only run with `RUN_EXTRA_DIAGNOSTICS=1`.

Useful options:

```bash
python run_experiment.py EXP-09 --max-windows 2
python run_experiment.py EXP-24 --feature-policy full
python run_experiment.py EXP-09 --data-dir /kaggle/input/northstar-v3-feature-export-fixed
```

Outputs are always written to `/kaggle/working` on Kaggle, or to
`tmp/kaggle_results/production_runs` locally.
