This sprint packages the full Northstar V3 7-day research plan into two self-contained Kaggle notebooks: `track_a_classical/notebook_track_a.ipynb` for the classical model stack and `track_b_frontier/notebook_track_b.ipynb` for the frontier architecture stack. Both notebooks load the same exported Northstar validation dataset, run the same walk-forward windows and promotion gates, save day-by-day JSON artifacts plus a final memo, and are meant to be launched as separate Kaggle GPU notebooks in parallel so their final verdicts can be compared directly.

Track A now supports the updated experiment knobs directly from environment variables:

- `TRACK_A_MODEL_FILTER=xgboost,lightgbm,catboost`
- `TRACK_A_FEATURE_MODE=full|reduced|protected_only`
- `TRACK_A_REDUCED_FEATURE_COUNT=60`
- `TRACK_A_NORMALIZE_RAW_FINANCIALS=1`
- `TRACK_A_REQUIRE_GROUP_RANKING=1`

Recommended reruns from the latest research cycle:

```bash
python3 scripts/kaggle/run_updated_track_a_experiments.py \
  --data-dir /path/to/northstar_export \
  --experiment tree_baseline \
  --profile full
```

```bash
python3 scripts/kaggle/run_updated_track_a_experiments.py \
  --data-dir /path/to/northstar_export \
  --experiment tree_reduced \
  --profile full
```

```bash
python3 scripts/kaggle/run_updated_track_a_experiments.py \
  --data-dir /path/to/northstar_export \
  --experiment sequence_reduced \
  --profile full
```

One-command local/Kaggle wrapper:

```bash
bash scripts/kaggle/run_updated_track_a_suite.sh \
  /kaggle/input/datasets/aryakghoshal/northstar-v4-validation-data \
  full
```

The updated Track A runner includes:

- mandatory per-date ranking groups for XGBoost / LightGBM / CatBoost
- LightGBM LambdaRank alongside XGBoost and CatBoost
- early-stopping validation splits for tree rankers
- reduced-feature runs sourced from day-1 IC rankings
- optional raw-financial normalization by `total_assets`
- GRU alongside LSTM / TCN / Transformer
